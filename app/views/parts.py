# app/views/parts.py
from flask import Blueprint, request, jsonify, current_app, send_file
from typing import Any, Optional
from datetime import datetime
from flask_login import login_required, current_user
from mongoengine.queryset.visitor import Q
from io import BytesIO
import re
import os

from app.models.part import Part
from app.models.job import Job
from app.models.order import Order
from app.models.bom import BOMLink
from app.extensions import csrf
from app.services.thumbs import thumb_urls_for, drawing_urls_for
from app.services.attrs import harvest_part_attrs
from app.models.artifact import PartFile
from app.models.extra_file import PartExtraFile
from app.views.whereused import _rows_for_child_pn
from app.services.processmeta import normalize_processes
from app.services.insights import (
    classify_part,
    normalized_processes as normalize_process_list,
    missing_fields as insights_missing_fields,
    recommended_deliverables,
)
from app.services.thumbs import preview_png_urls_for, drawing_png_urls_for
from app.services.filescan import discover_part_files, upsert_part_files
from app.services.thumbs_gen import generate_thumbs_for_parts
from app.services.extra_files import extra_file_url_for
from app.services.acl import (
    require_items_view,
    allowed_parts_for,
    part_is_allowed,
    user_has_permission,
    permissions_required,
    apply_job_scope,
    apply_order_scope,
)
from app.services.audit import log_action
from app.services.files_access import file_url_for, public_file_urls_enabled
from app.services.field_config import (
    context_field_ids,
    field_requires_runtime_scan,
    file_field_group,
    field_index as field_config_index,
    get_field_config,
    matches_field_filter_value,
    primary_query_path,
    query_paths_for_field,
    resolve_part_field_values,
)
from app.services.arena_export import build_arena_bom_csv, build_arena_file_links_csv
from app.services.parts_delete import delete_part_and_refs_cascade
from app.services.part_norm import clean_rev, clean_rev_or_none
from app.services.part_annotations import (
    add_part_comment,
    annotation_payload,
    filtered_part_attrs,
    migrate_legacy_annotations,
    set_part_notes,
)
#from app.services.user_profile import resolve_identity_profile, resolve_identity_profiles

from app.services.user_profile import (
    resolve_identity_profile,
    resolve_identity_profiles,
    profile_for_user,
)

bp = Blueprint("parts_api", __name__, url_prefix="/api")

def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in ("1", "true", "yes", "on")

def _clean_rev_value(value: object) -> str:
    return clean_rev(value)

def _clean_rev_input(value: object | None) -> str | None:
    return clean_rev_or_none(value)


def _normalized_revision(p: Part, attrs: dict) -> str:
    return _clean_rev_value(attrs.get("revision") or p.revision or "")


def _resolve_rev_for_pn(pn: str, rev: str | None) -> str:
    rev_clean = _clean_rev_input(rev)
    if rev_clean is not None:
        return rev_clean
    p = Part.objects(part_number__iexact=pn).order_by("-updated_at").first()
    if not p:
        return ""
    attrs = harvest_part_attrs(p)
    return _clean_rev_value(attrs.get("revision") or p.revision or "")


def _find_part_doc(pn: str, rev: str | None) -> Part | None:
    pn = (pn or "").strip()
    if not pn:
        return None
    rev_clean = _clean_rev_input(rev)
    if rev_clean is not None:
        return Part.objects(part_number__iexact=pn, revision__iexact=rev_clean).first()
    return Part.objects(part_number__iexact=pn).order_by("-updated_at").first()


def _deliverables_present(pn: str, rev: str | None) -> dict:
    groups = set()
    q = PartFile.objects(part_number__iexact=pn)
    rev_clean = _clean_rev_input(rev)
    if rev_clean is not None:
        q = q.filter(revision__iexact=rev_clean)
    for f in q.only("ext_group"):
        if f.ext_group:
            groups.add(f.ext_group.lower())
    return {
        "pdf": "pdf" in groups,
        "png": "png" in groups,
        "dxf": "dxf" in groups,
        "step": "step" in groups,
        "3mf": "3mf" in groups,
        "ply": "ply" in groups,
        "stl": "stl" in groups,
        "datasheet": "datasheet" in groups,
    }


def _where_used_stats(pn: str, rev: str | None) -> tuple[int, float]:
    q = BOMLink.objects(child_pn=pn)
    if rev is not None and "child_rev" in BOMLink._fields:
        q = q.filter(child_rev=_clean_rev_value(rev))
    parents = set()
    total_qty = 0.0
    for l in q.only("parent_pn", "parent_rev", "qty"):
        parents.add(((l.parent_pn or "").strip(), (l.parent_rev or "").strip()))
        total_qty += float(l.qty or 0)
    return len(parents), total_qty


def _has_bom_children(pn: str, rev: str | None) -> bool:
    q = BOMLink.objects(parent_pn=pn)
    if rev is not None and "parent_rev" in BOMLink._fields:
        q = q.filter(parent_rev=_clean_rev_value(rev))
    return q.limit(1).count() > 0


def _parent_candidates(child_pn: str, child_rev: str | None, max_rows: int = 50):
    q = BOMLink.objects(child_pn=child_pn)
    if child_rev is not None and "child_rev" in BOMLink._fields:
        q = q.filter(child_rev=_clean_rev_value(child_rev))
    parents = []
    for l in q.limit(max_rows):
        parent_pn = (getattr(l, "parent_pn", None) or "").strip()
        if not parent_pn:
            continue
        parent_rev = _clean_rev_value(getattr(l, "parent_rev", "") or "")
        parents.append((parent_pn, _resolve_rev_for_pn(parent_pn, parent_rev)))
    return parents


def _ancestor_paths(pn: str, rev: str | None, max_depth: int = 6):
    start = (pn, _resolve_rev_for_pn(pn, rev))
    queue = [(start, [start])]
    paths = []
    while queue:
        cur, path = queue.pop(0)
        if len(path) >= max_depth:
            paths.append(path)
            continue
        parents = _parent_candidates(cur[0], cur[1])
        if not parents:
            paths.append(path)
            continue
        for parent in parents:
            if parent in path:
                continue
            queue.append((parent, path + [parent]))
    if not paths:
        paths = [[start]]
    return paths


def _build_used_set(pairs: list[tuple[str, str | None]]):
    used = set()
    for pn, rev in pairs:
        pn_clean = (pn or "").strip()
        if not pn_clean:
            continue
        rev_clean = _clean_rev_value(rev)
        used.add((pn_clean.lower(), rev_clean.lower()))
    return used


def _match_used(used: set[tuple[str, str]], pn: str, rev: str | None) -> bool:
    pn_l = (pn or "").strip().lower()
    rev_l = _clean_rev_value(rev).lower()
    return (pn_l, rev_l) in used


def _part_label(pn: str, rev: str | None) -> dict:
    resolved_rev = _resolve_rev_for_pn(pn, rev)
    p = Part.objects(part_number__iexact=pn, revision__iexact=resolved_rev).first()
    attrs = harvest_part_attrs(p) if p else {}
    desc = (p.description if p else "") or attrs.get("description") or ""
    return {"pn": pn, "rev": resolved_rev, "desc": desc}


def _attr_identity(attrs: dict, *keys: str) -> str:
    for key in keys:
        value = str(attrs.get(key) or "").strip()
        if value:
            return value
    return ""


def _comment_payload(comment: dict, resolved: dict[str, dict[str, object]] | None = None) -> dict[str, object]:
    item = dict(comment or {})
    author = str(item.get("author") or "").strip()
    profile = None
    if author:
        if resolved is not None:
            profile = resolved.get(author.lower()) or resolve_identity_profile(author)
        else:
            profile = resolve_identity_profile(author)
    return {
        "ts": item.get("ts") or "",
        "author": author,
        "author_display": (profile or {}).get("label") or author or "User",
        "author_profile": profile or resolve_identity_profile(author),
        "text": str(item.get("text") or ""),
    }


def _display_revision_label(rev: str | None) -> str:
    rev_clean = _clean_rev_value(rev)
    return rev_clean or "(no revision)"


def _part_file_overview_row(pf: PartFile) -> dict[str, Any]:
    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")
    allow_public = public_file_urls_enabled()
    url = ""
    if allow_public and getattr(pf, "http_url", None):
        url = pf.http_url
    elif allow_public and http_base and getattr(pf, "rel_path", None):
        url = f"{http_base}/{pf.rel_path}"
    else:
        try:
            url = file_url_for(pf)
        except Exception:
            url = ""
    ext = str(getattr(pf, "ext", "") or "").strip().lower()
    name = os.path.basename(pf.rel_path or pf.path or "") or (f"{pf.ext_group}.{ext}" if pf.ext_group else "file")
    recorded_at = getattr(pf, "mtime_iso", None) or getattr(pf, "mtime", None) or getattr(pf, "discovered_at", None)
    return {
        "id": f"partfile:{pf.id}",
        "db_id": str(pf.id),
        "collection": "part_files",
        "kind": "scanned",
        "part_number": pf.part_number,
        "revision": _clean_rev_value(pf.revision or ""),
        "display_revision": _display_revision_label(pf.revision or ""),
        "name": name,
        "label": "",
        "ext_group": str(getattr(pf, "ext_group", "") or "").strip().lower(),
        "ext": ext,
        "mime": getattr(pf, "content_type", None) or "",
        "rel_path": pf.rel_path or "",
        "size": pf.size,
        "source": getattr(pf, "source", None) or "scan",
        "recorded_by": "",
        "recorded_at": recorded_at.isoformat() if recorded_at else "",
        "url": url,
    }


def _extra_file_overview_row(ef: PartExtraFile) -> dict[str, Any]:
    filename = (ef.original_name or "").strip() or os.path.basename(ef.rel_path or "") or "file"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "id": f"extra:{ef.id}",
        "db_id": str(ef.id),
        "collection": "part_extra_files",
        "kind": "extra",
        "part_number": ef.part_number,
        "revision": _clean_rev_value(ef.revision or ""),
        "display_revision": _display_revision_label(ef.revision or ""),
        "name": filename,
        "label": ef.label or "",
        "ext_group": "extra",
        "ext": ext,
        "mime": ef.mime or "",
        "rel_path": ef.rel_path or "",
        "size": ef.size,
        "source": ef.source or "upload",
        "recorded_by": ef.uploaded_by or "",
        "recorded_at": ef.uploaded_at.isoformat() if ef.uploaded_at else "",
        "url": extra_file_url_for(ef),
    }


def _group_file_overview_rows(rows: list[dict[str, Any]], current_rev: str) -> dict[str, Any]:
    def sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
        return (
            "0" if row.get("collection") == "part_files" else "1",
            str(row.get("ext_group") or ""),
            str(row.get("name") or ""),
        )

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        rev = _clean_rev_value(row.get("revision"))
        row["revision"] = rev
        row["display_revision"] = _display_revision_label(rev)
        grouped.setdefault(rev, []).append(row)

    def section_for(rev: str) -> dict[str, Any]:
        files = sorted(grouped.get(rev, []), key=sort_key)
        return {
            "revision": rev,
            "display_revision": _display_revision_label(rev),
            "counts": {
                "total": len(files),
                "part_files": sum(1 for row in files if row.get("collection") == "part_files"),
                "part_extra_files": sum(1 for row in files if row.get("collection") == "part_extra_files"),
            },
            "files": files,
        }

    other_revs = sorted(rev for rev in grouped.keys() if rev != current_rev)
    return {
        "current_revision": section_for(current_rev),
        "other_revisions": [section_for(rev) for rev in other_revs],
    }


def _jobs_orders_summary(pn: str, rev: str | None, user) -> list[dict]:
    paths = _ancestor_paths(pn, rev)
    is_admin = "admin" in {getattr(r, "name", "") for r in (user.roles or [])}
    can_jobs = is_admin or user_has_permission(user, "jobs.view")
    can_orders = is_admin or user_has_permission(user, "orders.view")

    job_q = Job.objects(is_deleted=False)
    if not can_jobs:
        job_q = Job.objects(id__in=[])
    else:
        job_q = apply_job_scope(job_q, user)

    order_q = Order.objects(status__ne="cancelled")
    if not can_orders:
        order_q = Order.objects(id__in=[])
    else:
        order_q = apply_order_scope(order_q, user)

    rows: list[dict] = []
    seen = set()

    for job in job_q:
        used_set = _build_used_set([(l.pn, l.rev) for l in (job.bom or [])])
        if not used_set:
            continue
        for path in paths:
            top_used = None
            for anc in reversed(path):
                if _match_used(used_set, anc[0], anc[1]):
                    top_used = anc
                    break
            if not top_used:
                continue
            immediate = top_used if top_used == path[0] else (path[1] if len(path) > 1 else path[0])
            key = ("job", str(job.id), immediate[0].lower(), immediate[1].lower(), top_used[0].lower(), top_used[1].lower())
            if key in seen:
                continue
            seen.add(key)
            imm = _part_label(immediate[0], immediate[1])
            top = _part_label(top_used[0], top_used[1])
            rows.append(
                {
                    "row_key": f"job:{job.id}:{imm['pn']}:{top['pn']}:{top['rev']}",
                    "source": "job",
                    "job_id": str(job.id),
                    "job_number": job.job_number,
                    "order_id": "",
                    "order_number": "",
                    "order_kind": "",
                    "order_status": "",
                    "immediate_pn": imm["pn"],
                    "immediate_rev": imm["rev"],
                    "immediate_desc": imm["desc"],
                    "top_pn": top["pn"],
                    "top_rev": top["rev"],
                    "top_desc": top["desc"],
                }
            )

    for order in order_q:
        used_set = _build_used_set([(l.pn, l.rev) for l in (order.lines or [])])
        if not used_set:
            continue
        for path in paths:
            top_used = None
            for anc in reversed(path):
                if _match_used(used_set, anc[0], anc[1]):
                    top_used = anc
                    break
            if not top_used:
                continue
            immediate = top_used if top_used == path[0] else (path[1] if len(path) > 1 else path[0])
            key = ("order", str(order.id), immediate[0].lower(), immediate[1].lower(), top_used[0].lower(), top_used[1].lower())
            if key in seen:
                continue
            seen.add(key)
            imm = _part_label(immediate[0], immediate[1])
            top = _part_label(top_used[0], top_used[1])
            rows.append(
                {
                    "row_key": f"order:{order.id}:{imm['pn']}:{top['pn']}:{top['rev']}",
                    "source": "order",
                    "job_id": str(order.job.id) if order.job else "",
                    "job_number": order.job.job_number if order.job else "",
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                    "order_kind": order.kind,
                    "order_status": order.status,
                    "immediate_pn": imm["pn"],
                    "immediate_rev": imm["rev"],
                    "immediate_desc": imm["desc"],
                    "top_pn": top["pn"],
                    "top_rev": top["rev"],
                    "top_desc": top["desc"],
                }
            )

    rows.sort(key=lambda r: (r.get("job_number") or "", r.get("order_number") or "", r.get("source")))
    return rows


def _context_field_values(
    part: Part | None,
    context_name: str,
    *,
    coverage: set[str] | None = None,
    extra: dict | None = None,
):
    config = get_field_config()
    attrs = harvest_part_attrs(part) if part else {}
    values = resolve_part_field_values(
        part,
        context_field_ids(context_name, config),
        attrs=attrs,
        config=config,
        extra=extra,
        coverage=coverage,
    )
    return config, attrs, values


_EMPTY_VALUES = {"", "n/a", "na", "none", "null", "0", "false"}

def _is_blankish(value: object, *, allow_na: bool = False) -> bool:
    if value is None:
        return True
    text = str(value).strip().lower()
    if allow_na and text in ("n/a", "na"):
        return False
    return text in _EMPTY_VALUES

_REQUIRED_ALWAYS = {"pdf"}
_REQUIRED_BY_PROCESS = {
    "machine": {"step"},
    "3d print": {"step", "3mf"},
    "3d laser": {"step"},
    "folding": {"dxf", "png", "step"},
    "rolling": {"dxf", "png", "step"},
    "lasercut": {"dxf", "png"},
    "profile cut": {"dxf", "png"},
    "cutting": {"dxf", "png"},
    "waterjet": {"dxf", "png"},
    "plasma": {"dxf", "png"},
}

def _norm_file_group(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in ("stp", "step"):
        return "step"
    if text in ("jpg", "jpeg"):
        return "png"
    return text

def _required_files_for_processes(proc_list: list[str], meta: dict) -> set[str]:
    required: set[str] = set(_REQUIRED_ALWAYS)
    for p in proc_list or []:
        entry = meta.get(p) or {}
        explicit_for_process = False
        if isinstance(entry, dict):
            for key in ("required_files", "files_required", "files", "file_groups", "file_groups_required"):
                vals = entry.get(key)
                if not vals:
                    continue
                explicit_for_process = True
                if isinstance(vals, (str, bytes)):
                    vals = [vals]
                for v in vals:
                    g = _norm_file_group(v)
                    if g:
                        required.add(g)
        if not explicit_for_process:
            required.update(_REQUIRED_BY_PROCESS.get(p, set()))
    return {g for g in required if g}

def _full_files_ok(proc_list: list[str], groups: set[str], meta: dict) -> bool:
    if not proc_list:
        return False
    required = _required_files_for_processes(proc_list, meta)
    if not required:
        return False
    return required.issubset(groups or set())

def _min_props_ok(part: Part, attrs: dict, proc_list: list[str]) -> bool:
    if not (part.part_number or "").strip():
        return False
    desc = part.description or attrs.get("description") or ""
    if _is_blankish(desc):
        return False
    rev = _clean_rev_value(attrs.get("revision") or part.revision or "")
    if not rev:
        return False
    material = attrs.get("material") or attrs.get("Material") or ""
    if _is_blankish(material, allow_na=True):
        return False
    finish = attrs.get("finish") or attrs.get("Finish") or ""
    if _is_blankish(finish, allow_na=True):
        return False
    if not proc_list:
        return False
    return True

@login_required
@require_items_view
@bp.route("/parts_lazy", methods=["GET", "POST"])
@csrf.exempt
def parts_lazy():
    body = request.get_json(force=True, silent=True) or {}
    first = int(body.get("first", 0))
    rows = int(body.get("rows", 25))
    sort_field = (body.get("sortField") or "part_number")
    sort_order = int(body.get("sortOrder", 1))  # 1 asc, -1 desc
    filters = body.get("filters", {})

    field_config = get_field_config()
    parts_field_ids = context_field_ids("parts_list", field_config)
    field_meta = field_config_index(field_config)
    runtime_filter_ids = {field_id for field_id in parts_field_ids if field_requires_runtime_scan(field_id, field_config)}
    sortable_ids = {field_id for field_id in parts_field_ids if field_meta.get(field_id, {}).get("sortable")}
    filterable_ids = {field_id for field_id in parts_field_ids if field_meta.get(field_id, {}).get("filterable")}
    if sort_field not in sortable_ids:
        sort_field = "part_number"
    runtime_sort = field_requires_runtime_scan(sort_field, field_config)
    mapped = None if runtime_sort else primary_query_path(sort_field, field_config)
    if not runtime_sort and not mapped:
        sort_field = "part_number"
        mapped = primary_query_path(sort_field, field_config) or "part_number"
    order_by = f"-{mapped}" if mapped and sort_order == -1 else (mapped or "part_number")

    def _terms(s: str):
        return [t for t in re.split(r"\s+", (s or "").strip().lower()) if t]

    _missing = object()

    def _filter_value(key: str, default: Any = _missing):
        raw = filters.get(key)
        if not isinstance(raw, dict):
            return default
        if "value" in raw:
            return raw.get("value")
        constraints = raw.get("constraints")
        if isinstance(constraints, list):
            for item in constraints:
                if not isinstance(item, dict) or "value" not in item:
                    continue
                value = item.get("value")
                if value not in (None, ""):
                    return value
                if isinstance(value, bool):
                    return value
        return default

    def add_filter(q: Q, key: str, *fields):
        raw_value = _filter_value(key, "")
        val = str(raw_value or "").strip()
        if not val or val.startswith("__"):
            return q
        for t in _terms(val):
            or_q = Q()
            for fld in fields:
                or_q = or_q | Q(**{f"{fld}__icontains": t})
            q = q & or_q
        return q

    def add_field_filter(q: Q, key: str):
        if key not in filterable_ids:
            return q
        raw_value = _filter_value(key, "")
        val = str(raw_value or "").strip()
        if not val or val.startswith("__"):
            return q
        paths = query_paths_for_field(key, field_config)
        if not paths:
            return q
        for t in _terms(val):
            or_q = Q()
            for fld in paths:
                or_q = or_q | Q(**{f"{fld}__icontains": t})
            q = q & or_q
        return q

    def _bool_filter_value(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        text = str(value).strip().lower()
        if not text:
            return None
        if text in ("1", "true", "yes", "y", "on"):
            return True
        if text in ("0", "false", "no", "n", "off", "missing"):
            return False
        return None

    def _number_filter(value: Any) -> tuple[str, float, float | None] | None:
        text = str(value or "").strip()
        if not text:
            return None
        range_match = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*(?:\.\.|to|-)\s*(-?\d+(?:\.\d+)?)\s*$", text, re.I)
        if range_match:
            left = float(range_match.group(1))
            right = float(range_match.group(2))
            return ("range", min(left, right), max(left, right))
        compare_match = re.match(r"^\s*(<=|>=|=|<|>)?\s*(-?\d+(?:\.\d+)?)\s*$", text)
        if compare_match:
            op = compare_match.group(1) or "="
            target = float(compare_match.group(2))
            return (op, target, None)
        return None

    def add_typed_field_filter(q: Q, key: str, data_type: str, raw_value: Any):
        paths = query_paths_for_field(key, field_config)
        if not paths:
            return None

        if data_type == "boolean":
            expected = _bool_filter_value(raw_value)
            if expected is None:
                return add_field_filter(q, key)
            or_q = Q()
            for fld in paths:
                or_q = or_q | Q(**{fld: expected})
            return q & or_q

        if data_type == "number":
            parsed = _number_filter(raw_value)
            path = primary_query_path(key, field_config)
            if parsed is None or not path:
                return add_field_filter(q, key)
            op, start, end = parsed
            if op == "range":
                return q & Q(**{f"{path}__gte": start}) & Q(**{f"{path}__lte": end})
            if op == ">":
                return q & Q(**{f"{path}__gt": start})
            if op == ">=":
                return q & Q(**{f"{path}__gte": start})
            if op == "<":
                return q & Q(**{f"{path}__lt": start})
            if op == "<=":
                return q & Q(**{f"{path}__lte": start})
            return q & Q(**{path: start})

        return add_field_filter(q, key)

    def _flag_enabled(key: str) -> bool:
        val = _filter_value(key)
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        return str(val).strip().lower() in ("true", "1", "yes", "y", "on")

    def _or_contains(paths: list[str], term: str) -> Q:
        out = Q()
        for fld in paths:
            out = out | Q(**{f"{fld}__icontains": term})
        return out

    def _or_array_regex(field: str, term: str) -> Q:
        if not term:
            return Q()
        return Q(__raw__={field: {"$regex": re.escape(term), "$options": "i"}})

    def _pairs_q(pairs: set[tuple[str, str]]):
        pair_q = Q()
        for pn, rev in pairs:
            pn_clean = (pn or "").strip()
            if not pn_clean:
                continue
            rev_clean = _clean_rev_value(rev)
            pair_q = pair_q | Q(part_number__iexact=pn_clean, revision__iexact=rev_clean)
        return pair_q

    def _exclude_pairs_q(pairs: set[tuple[str, str]]) -> Q:
        clauses: list[dict[str, object]] = []
        for pn, rev in pairs:
            pn_clean = (pn or "").strip()
            if not pn_clean:
                continue
            rev_clean = _clean_rev_value(rev)
            clauses.append(
                {
                    "part_number": {"$regex": f"^{re.escape(pn_clean)}$", "$options": "i"},
                    "revision": {"$regex": f"^{re.escape(rev_clean)}$", "$options": "i"},
                }
            )
        if not clauses:
            return Q()
        return Q(__raw__={"$nor": clauses})

    def _file_pairs_for_group(group: str) -> set[tuple[str, str]]:
        pairs: set[tuple[str, str]] = set()
        group_norm = _norm_file_group(group)
        if not group_norm:
            return pairs
        for row in PartFile.objects(ext_group=group_norm).only("part_number", "revision"):
            pn_clean = (getattr(row, "part_number", None) or "").strip()
            if not pn_clean:
                continue
            pairs.add((pn_clean, _clean_rev_value(getattr(row, "revision", "") or "")))
        return pairs

    def _approval_q(expected: bool) -> Q:
        empty_values = [None, "", "n/a", "N/A", "na", "NA", "none", "None", "null", "NULL", "0", "false", "False", "FALSE"]
        keys = ["attrs.approvedby", "attrs.approved_by", "attrs.approved"]
        if expected:
            return Q(
                __raw__={
                    "$or": [
                        {key: {"$exists": True, "$nin": empty_values}}
                        for key in keys
                    ]
                }
            )
        return Q(
            __raw__={
                "$and": [
                    {
                        "$or": [
                            {key: {"$exists": False}},
                            {key: {"$in": empty_values}},
                        ]
                    }
                    for key in keys
                ]
            }
        )

    q = Q()
    parts_context_ids = context_field_ids("parts_list", field_config)
    generic_filter_ids = []
    typed_filter_specs: list[tuple[str, str, Any]] = []
    runtime_filter_specs: list[tuple[str, str, Any]] = []
    for field_id in filterable_ids:
        if field_id in {"material", "process"}:
            continue
        data_type = str(field_meta.get(field_id, {}).get("data_type") or "text")
        raw_value = _filter_value(field_id)
        if data_type == "image":
            continue
        if data_type in {"boolean", "number"}:
            if raw_value is not _missing and raw_value not in (None, ""):
                if data_type == "boolean" and field_id == "approved":
                    expected = _bool_filter_value(raw_value)
                    if expected is not None:
                        q = q & _approval_q(expected)
                        continue
                if data_type == "boolean":
                    file_group = file_field_group(field_id)
                    if file_group:
                        expected = _bool_filter_value(raw_value)
                        if expected is not None:
                            pairs = _file_pairs_for_group(file_group)
                            if expected and not pairs:
                                return jsonify({"data": [], "totalRecords": 0})
                            if pairs:
                                q = q & (_pairs_q(pairs) if expected else _exclude_pairs_q(pairs))
                            continue
                if field_id in runtime_filter_ids:
                    typed_filter_specs.append((field_id, data_type, raw_value))
                else:
                    next_q = add_typed_field_filter(q, field_id, data_type, raw_value)
                    if next_q is None:
                        typed_filter_specs.append((field_id, data_type, raw_value))
                    else:
                        q = next_q
            continue
        if field_id in runtime_filter_ids:
            if raw_value is not _missing and raw_value not in (None, ""):
                runtime_filter_specs.append((field_id, data_type, raw_value))
            continue
        generic_filter_ids.append(field_id)
    for field_id in generic_filter_ids:
        q = add_field_filter(q, field_id)
    material_val = _filter_value("material", "")
    material_val_norm = str(material_val or "").strip().lower()
    if material_val_norm not in ("__missing__", "missing", "(missing)"):
        if "material" in runtime_filter_ids and material_val not in (None, ""):
            runtime_filter_specs.append(("material", str(field_meta.get("material", {}).get("data_type") or "text"), material_val))
        else:
            q = add_field_filter(q, "material")
    finish_val = _filter_value("finish", "")
    if "finish" in runtime_filter_ids and finish_val not in (None, ""):
        runtime_filter_specs.append(("finish", str(field_meta.get("finish", {}).get("data_type") or "text"), finish_val))
    else:
        q = add_field_filter(q, "finish")
    meta = current_app.config.get("PROCESS_META", {}) or {}

    def _process_filter_q(text: str) -> Q:
        raw_text = str(text or "").strip()
        if not raw_text:
            return Q()

        normalized_terms = normalize_processes({"processes": [raw_text]}, meta)
        raw_terms = _terms(raw_text)
        if raw_text.lower() not in raw_terms:
            raw_terms.insert(0, raw_text.lower())

        or_q = Q()
        if normalized_terms:
            or_q = or_q | Q(processes__in=normalized_terms)
        for term in raw_terms:
            or_q = (
                or_q
                | _or_array_regex("processes", term)
                | Q(attrs__process__icontains=term)
                | Q(attrs__process2__icontains=term)
                | Q(attrs__process3__icontains=term)
                | Q(attrs__processes__icontains=term)
                | Q(canonical__processes__icontains=term)
            )
        return or_q

    category_paths = query_paths_for_field("category", field_config) or ["attrs__category", "category"]
    material_paths = query_paths_for_field("material", field_config) or ["attrs__material"]
    proc_key = "process" if "process" in filters else "processes"
    proc_val = _filter_value(proc_key, "")
    proc_val_norm = str(proc_val or "").strip().lower()
    if proc_val_norm in ("hardware", "fastener", "fasteners"):
        q = q & (
            _process_filter_q("hardware")
            | _or_contains(category_paths, "hardware")
        )
    elif proc_val_norm in ("sheet metal", "sheetmetal", "sheet"):
        q = q & (
            _process_filter_q(proc_val_norm)
            | _or_contains(category_paths, "sheet")
            | _or_contains(material_paths, "sheet")
        )
    else:
        if proc_val_norm:
            q = q & _process_filter_q(proc_val_norm)
    g = _filter_value("global", "")

    if g:
        global_paths: list[str] = []
        for field_id in parts_field_ids:
            if field_id == "process":
                continue
            if field_id in runtime_filter_ids:
                continue
            for fld in query_paths_for_field(field_id, field_config):
                if fld not in global_paths:
                    global_paths.append(fld)

        for t in _terms(str(g)):
            orq = _process_filter_q(t)
            for fld in global_paths:
                orq = orq | Q(**{f"{fld}__icontains": t})
            q = q & orq

    # Optional job filter: limit to BOM parts for that job unless explicitly bypassed
    job_id = body.get("job") or request.args.get("job")
    job_filter_enabled = bool(job_id) and str(body.get("job_only", "true")).lower() != "false"
    if job_filter_enabled and job_id:
        job = Job.objects(id=job_id).first()
        if job and job.bom:
            pairs = set()
            for line in job.bom:
                pn_line = (line.pn or "").strip()
                if not pn_line:
                    continue
                pairs.add((pn_line, _clean_rev_value(line.rev)))
            if pairs:
                q = q & _pairs_q(pairs)

    # Optional "used in job" filter (with optional job number substring)
    used_in_job = _flag_enabled("used_in_job")
    job_number_filter = str(_filter_value("job_number", "") or "").strip()
    if used_in_job:
        job_qs = Job.objects(is_deleted=False)
        if job_number_filter:
            job_qs = job_qs.filter(job_number__icontains=job_number_filter)
        pairs = set()
        for j in job_qs.only("bom"):
            for line in (j.bom or []):
                pn_line = (line.pn or "").strip()
                if not pn_line:
                    continue
                pairs.add((pn_line, _clean_rev_value(line.rev)))
        if not pairs:
            return jsonify({"data": [], "totalRecords": 0})
        q = q & _pairs_q(pairs)

    # ACL filter for restricted viewers
    allowed_scope = allowed_parts_for(current_user)
    if isinstance(allowed_scope, set):
        if not allowed_scope:
            return jsonify({"data": [], "totalRecords": 0})
        allowed_q = Q()
        for pn, rev in allowed_scope:
            pn_clean = (pn or "").strip()
            if not pn_clean:
                continue
            if rev:
                allowed_q = allowed_q | Q(part_number__iexact=pn_clean, revision__iexact=rev)
            else:
                allowed_q = allowed_q | Q(part_number__iexact=pn_clean)
        q = q & allowed_q

    qs = Part.objects(q)

    if material_val_norm in ("__missing__", "missing", "(missing)"):
        material_query = (primary_query_path("material", field_config) or "attrs__material").replace("__", ".")
        qs = qs.filter(
            __raw__={
                "$or": [
                    {material_query: {"$exists": False}},
                    {material_query: ""},
                    {material_query: None},
                ]
            }
        )

    full_files_filter = _flag_enabled("full_files")
    approved_only_filter = _flag_enabled("approved_only")
    min_props_filter = _flag_enabled("min_props")

    if approved_only_filter:
        qs = qs.filter(_approval_q(True))

    def _coverage_map(parts_list: list[Part]) -> dict[tuple[str, str], set[str]]:
        if not parts_list:
            return {}
        pn_list = list({p.part_number for p in parts_list if p.part_number})
        qf = PartFile.objects(part_number__in=pn_list)
        coverage: dict[tuple[str, str], set[str]] = {}
        for f in qf.only("part_number", "revision", "ext_group"):
            key = (f.part_number, _clean_rev_value(f.revision or ""))
            coverage.setdefault(key, set()).add((f.ext_group or "").lower())
        return coverage

    needs_scan = any([
        full_files_filter,
        min_props_filter,
        bool(typed_filter_specs),
        bool(runtime_filter_specs),
        runtime_sort,
    ])

    if needs_scan:
        scan_order_by = order_by if not runtime_sort else "part_number"
        all_docs = list(
            qs.order_by(scan_order_by).only("part_number", "revision", "description", "category", "attrs", "processes")
        )
        scan_requires_coverage = bool(full_files_filter)
        if not scan_requires_coverage:
            scan_requires_coverage = any(bool(file_field_group(field_id)) for field_id, _data_type, _raw_value in typed_filter_specs)
        if not scan_requires_coverage:
            scan_requires_coverage = any(bool(file_field_group(field_id)) for field_id, _data_type, _raw_value in runtime_filter_specs)
        if not scan_requires_coverage and runtime_sort:
            scan_requires_coverage = bool(file_field_group(sort_field))

        scan_requires_values = bool(runtime_sort or typed_filter_specs or runtime_filter_specs)
        coverage = _coverage_map(all_docs) if scan_requires_coverage else {}
        filtered_docs = []
        resolved_cache: dict[tuple[str, str], dict[str, Any]] = {}
        for p in all_docs:
            attrs = harvest_part_attrs(p)
            rev = _normalized_revision(p, attrs)
            groups = coverage.get((p.part_number, rev)) or set()
            proc_list = normalize_process_list(attrs, list(p.processes or []), meta)
            if min_props_filter and not _min_props_ok(p, attrs, proc_list):
                continue
            if full_files_filter and not _full_files_ok(proc_list, groups, meta):
                continue
            key = (p.part_number, rev)
            values: dict[str, Any] = {}
            if scan_requires_values:
                values = resolve_part_field_values(
                    p,
                    parts_context_ids,
                    attrs=attrs,
                    config=field_config,
                    extra={"part_number": p.part_number, "revision": rev},
                    coverage=groups if scan_requires_coverage else None,
                )
            typed_match = True
            for field_id, data_type, raw_value in typed_filter_specs:
                if not matches_field_filter_value(values.get(field_id), raw_value, data_type):
                    typed_match = False
                    break
            if not typed_match:
                continue
            runtime_match = True
            for field_id, data_type, raw_value in runtime_filter_specs:
                if not matches_field_filter_value(values.get(field_id), raw_value, data_type):
                    runtime_match = False
                    break
            if not runtime_match:
                continue
 
            if values:
                resolved_cache[key] = values
            filtered_docs.append(p)
        if runtime_sort:
            sort_type = str((field_meta.get(sort_field) or {}).get("data_type") or "text")
            reverse = (sort_order == -1)

            def _runtime_sort_key(doc: Part):
                attrs = harvest_part_attrs(doc)
                rev = _normalized_revision(doc, attrs)
                values = resolved_cache.get((doc.part_number, rev)) or {}
                value = values.get(sort_field)
                if sort_type == "number":
                    try:
                        return float(value)
                    except Exception:
                        return float("-inf") if reverse else float("inf")
                if sort_type == "boolean":
                    return 1 if bool(value) else 0
                return str(value or "").lower()

            filtered_docs.sort(key=_runtime_sort_key, reverse=reverse)
        filtered = len(filtered_docs)
        docs = filtered_docs[first:first + rows]
    else:
        filtered = qs.count()
        docs = list(
            qs.order_by(order_by)
            .only("part_number", "revision", "description", "category", "attrs", "processes")
            .skip(first)
            .limit(rows)
        )
        coverage = _coverage_map(docs)
        resolved_cache = {}

    out = []
    for p in docs:
        attrs = harvest_part_attrs(p)
        pn = p.part_number
        rev = _normalized_revision(p, attrs)
        groups = coverage.get((pn, rev)) or set()
        process_list = normalize_process_list(attrs, list(p.processes or []), current_app.config.get("PROCESS_META", {}))
        thumb_list = thumb_urls_for(pn, rev)
        values = dict(resolved_cache.get((pn, rev)) or {})
        if not values:
            values = resolve_part_field_values(
                p,
                parts_context_ids,
                attrs=attrs,
                config=field_config,
                extra={"part_number": pn, "revision": rev, "thumbnail": thumb_list[0] if thumb_list else ""},
                coverage=groups,
            )
        elif thumb_list:
            values["thumbnail"] = thumb_list[0]
        values["display_code"] = f"{pn}-{rev}" if rev else pn
        out.append(
            {
                "id": f"{pn}::{rev}",
                "part_number": values.get("part_number", pn),
                "revision": values.get("revision", rev),
                "display_code": values.get("display_code", f"{pn}-{rev}" if rev else pn),
                "description": values.get("description", ""),
                "category": values.get("category", ""),
                "material": values.get("material", ""),
                "finish": values.get("finish", ""),
                "mass": values.get("mass", ""),
                "process": values.get("process", ""),
                "processes": process_list,
                "thumb_urls": thumb_list,
                "has_pdf": bool(values.get("has_pdf", "pdf" in groups)),
                "has_png": bool(values.get("has_png", "png" in groups)),
                "has_dxf": bool(values.get("has_dxf", "dxf" in groups)),
                "has_step": bool(values.get("has_step", "step" in groups)),
                "has_edr": bool(values.get("has_edr", "edr" in groups)),
                "has_3mf": bool(values.get("has_3mf", "3mf" in groups)),
                "has_ply": bool(values.get("has_ply", "ply" in groups)),
                "has_stl": bool(values.get("has_stl", "stl" in groups)),
                "has_datasheet": bool(values.get("has_datasheet", "datasheet" in groups)),
                **values,
            }
        )

    try:
        log_action("parts.list", resource_type="parts", resource=f"first={first},rows={rows}")
    except Exception:
        pass

    return jsonify({"data": out, "totalRecords": filtered})


@bp.get("/part_detail")
@login_required
@require_items_view
def part_detail():
    pn = (request.args.get("pn") or "").strip()
    p = None
    if "rev" in request.args:
        rev = request.args.get("rev")
        rev_clean = _clean_rev_input(rev)
        p = Part.objects(part_number__iexact=pn, revision__iexact=(rev_clean or "")).first()
    else:
        p = Part.objects(part_number__iexact=pn).order_by("-updated_at").first()
    if not p:
        return jsonify({"error": "not found"}), 404

    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, p.part_number, p.revision or ""):
            try:
                log_action("part.view.deny", resource_type="part", resource=f"{p.part_number}:{p.revision or ''}")
            except Exception:
                pass
            return jsonify({"error": "forbidden"}), 403
    except Exception:
        pass

    attrs = harvest_part_attrs(p)
    notes_comments = annotation_payload(p, attrs)
    visible_attrs = filtered_part_attrs(p)
    norm_rev = _normalized_revision(p, attrs)
    meta = current_app.config.get("PROCESS_META", {})
    proc_list = normalize_process_list(attrs, list(p.processes or []), meta)
    _, _, summary_field_values = _context_field_values(
        p,
        "part_detail_summary",
        extra={"part_number": p.part_number, "revision": norm_rev},
    )

    preview_urls = preview_png_urls_for(p.part_number, norm_rev)
    drawing_urls = drawing_png_urls_for(p.part_number, norm_rev)

    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")
    allow_public = public_file_urls_enabled()

    def to_url(f: PartFile):
        if allow_public and getattr(f, "http_url", None):
            return f.http_url
        if allow_public and http_base and f.rel_path:
            return f"{http_base}/{f.rel_path}"
        return file_url_for(f)

    def file_label(f: PartFile) -> str:
        name = os.path.basename(f.rel_path or f.path or "")
        return name or "file"

    files = {"pdf": [], "dxf": [], "step": [], "edr": [], "3mf": [], "ply": [], "stl": []}
    for f in (
        PartFile.objects(part_number__iexact=p.part_number, revision__iexact=norm_rev)
        .only("ext_group", "rel_path", "path", "http_url")
        .order_by("ext_group", "rel_path")
    ):
        if f.ext_group in files:
            files[f.ext_group].append({"url": to_url(f), "rel": f.rel_path or "", "name": file_label(f)})

    uploader_identity = _attr_identity(attrs, "uploader", "uploaded_by", "uploadedby", "author", "drawnby")
    approver_identity = _attr_identity(attrs, "approvedby", "approved_by", "approved", "checkedby")
    raw_comments = list(notes_comments.get("comments") or [])
    identity_keys = [uploader_identity, approver_identity]
    identity_keys.extend(str((comment or {}).get("author") or "").strip() for comment in raw_comments)
    resolved_profiles = resolve_identity_profiles(identity_keys)
    comments = [_comment_payload(comment, resolved_profiles) for comment in raw_comments]
    uploader_profile = resolve_identity_profile(uploader_identity) if uploader_identity else None
    if uploader_identity:
        uploader_profile = resolved_profiles.get(uploader_identity.lower(), uploader_profile)
    approver_profile = resolve_identity_profile(approver_identity) if approver_identity else None
    if approver_identity:
        approver_profile = resolved_profiles.get(approver_identity.lower(), approver_profile)

    wu_rows = _rows_for_child_pn(p.part_number, p.revision)

    other_versions = []
    pn_key = p.part_number
    for op in (
        Part.objects(part_number__iexact=pn)
        .only("part_number", "revision", "description", "category", "attrs", "updated_at")
        .order_by("-updated_at")
    ):
        attrs_v = harvest_part_attrs(op)
        rev_v = _normalized_revision(op, attrs_v)
        other_versions.append(
            {
                "id": f"{pn_key}::{rev_v}",
                "part_number": pn_key,
                "revision": rev_v,
                "display_code": f"{pn_key}-{rev_v}" if rev_v else pn_key,
                "description": op.description or attrs_v.get("description") or "",
                "thumb_urls": thumb_urls_for(pn_key, rev_v),
            }
        )

    jobs_orders = _jobs_orders_summary(p.part_number, norm_rev, current_user)

    try:
        log_action(
            action="part.view",
            resource_type="part",
            resource=f"{p.part_number}:{p.revision or ''}",
        )
    except Exception:
        pass

    can_jobs_manage = user_has_permission(current_user, "jobs.manage")
    can_orders_manage = user_has_permission(current_user, "orders.manage")
    can_parts_delete = user_has_permission(current_user, "items.edit")
    can_parts_edit = can_parts_delete
    can_parts_note = user_has_permission(current_user, "items.view")

    return jsonify(
        {
            "part": {
                "part_number": p.part_number,
                "description": summary_field_values.get("description", p.description or attrs.get("description", "")),
                "revision": norm_rev,
                "display_code": f"{p.part_number}-{norm_rev}" if norm_rev else p.part_number,
                "category": summary_field_values.get("category", attrs.get("category", "")),
                "material": summary_field_values.get("material", attrs.get("material", "")),
                "finish": summary_field_values.get("finish", attrs.get("finish", "")),
                "mass": summary_field_values.get("mass", attrs.get("mass", "")),
                "process": summary_field_values.get("process", ", ".join(proc_list)),
                "processes": proc_list,
                "notes": str(notes_comments.get("notes") or ""),
                "field_values": summary_field_values,
                "attributes": visible_attrs,
            },
            "images": preview_urls,
            "drawing_urls": drawing_urls,
            "files": files,
            "uploader_profile": uploader_profile,
            "approver_profile": approver_profile,
            "comments": comments,
            "whereused": wu_rows,
            "other_versions": other_versions,
            "jobs_orders": jobs_orders,
            "can_jobs_manage": can_jobs_manage,
            "can_orders_manage": can_orders_manage,
            "can_parts_delete": can_parts_delete,
            "can_parts_edit": can_parts_edit,
            "can_parts_note": can_parts_note,
            "arena_file_link_base_url": current_app.config.get("ARENA_FILE_LINK_BASE_URL", ""),
        }
    )


def _request_list_value(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if value is None:
        value = request.form.getlist(key)
        if not value:
            value = request.args.getlist(key)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    text = str(value or "").strip()
    if not text:
        return []
    return [text]


@bp.post("/parts/<path:pn>/export/arena_bom")
@csrf.exempt
@login_required
@require_items_view
def export_arena_bom(pn: str):
    payload = request.get_json(silent=True) or {}
    rev = payload.get("rev")
    if rev is None and "rev" in request.form:
        rev = request.form.get("rev")
    if rev is None and "rev" in request.args:
        rev = request.args.get("rev")

    part = _find_part_doc(pn, rev)
    if not part:
        return jsonify({"error": "not found"}), 404

    allowed = None
    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, part.part_number, part.revision or ""):
            return jsonify({"error": "forbidden"}), 403
    except Exception:
        allowed = None

    attrs = harvest_part_attrs(part)
    norm_rev = _normalized_revision(part, attrs)
    field_ids = _request_list_value(payload, "field_ids")
    try:
        name, data = build_arena_bom_csv(
            part.part_number,
            norm_rev,
            field_ids=field_ids,
            is_allowed=(lambda child_pn, child_rev: part_is_allowed(allowed, child_pn, child_rev or "")) if isinstance(allowed, set) else None,
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        log_action(
            "arena.export.bom",
            resource_type="part",
            resource=f"{part.part_number}:{norm_rev}",
            meta={"field_count": len(field_ids)},
        )
    except Exception:
        pass

    return send_file(
        BytesIO(data),
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name=name,
    )


@bp.post("/parts/<path:pn>/export/arena_file_links")
@csrf.exempt
@login_required
@require_items_view
def export_arena_file_links(pn: str):
    payload = request.get_json(silent=True) or {}
    rev = payload.get("rev")
    if rev is None and "rev" in request.form:
        rev = request.form.get("rev")
    if rev is None and "rev" in request.args:
        rev = request.args.get("rev")

    part = _find_part_doc(pn, rev)
    if not part:
        return jsonify({"error": "not found"}), 404

    allowed = None
    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, part.part_number, part.revision or ""):
            return jsonify({"error": "forbidden"}), 403
    except Exception:
        allowed = None

    attrs = harvest_part_attrs(part)
    norm_rev = _normalized_revision(part, attrs)
    base_url = str(
            payload.get("base_url")
            or request.form.get("base_url")
            or request.args.get("base_url")
            or current_app.config.get("ARENA_FILE_LINK_BASE_URL")
            or ""
                ).strip()
    try:
        
        profile = profile_for_user(current_user)
        author = str(
            profile.get("display_name")
            or profile.get("email")
            or getattr(current_user, "email", "")
            or ""
        ).strip()
        name, data = build_arena_file_links_csv(
            part.part_number,
            norm_rev,
            base_url=base_url,
            author=author,
            is_allowed=(lambda child_pn, child_rev: part_is_allowed(allowed, child_pn, child_rev or "")) if isinstance(allowed, set) else None,
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        log_action(
            "arena.export.files",
            resource_type="part",
            resource=f"{part.part_number}:{norm_rev}",
            meta={"base_url": base_url},
        )
    except Exception:
        pass

    return send_file(
        BytesIO(data),
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name=name,
    )


@bp.get("/parts/<path:pn>/files_overview")
@login_required
@require_items_view
def part_files_overview(pn: str):
    pn = (pn or "").strip()
    rev = request.args.get("rev")
    p = _find_part_doc(pn, rev)
    if not p:
        return jsonify({"error": "not found"}), 404

    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, p.part_number, p.revision or ""):
            return jsonify({"error": "forbidden"}), 403
    except Exception:
        allowed = None

    attrs = harvest_part_attrs(p)
    current_rev = _normalized_revision(p, attrs)
    rows: list[dict[str, Any]] = []

    for pf in (
        PartFile.objects(part_number__iexact=p.part_number)
        .only(
            "part_number",
            "revision",
            "ext_group",
            "ext",
            "rel_path",
            "path",
            "http_url",
            "size",
            "mtime_iso",
            "mtime",
            "discovered_at",
            "content_type",
            "source",
        )
        .order_by("revision", "ext_group", "rel_path")
    ):
        row_rev = _clean_rev_value(pf.revision or "")
        if isinstance(allowed, set) and not part_is_allowed(allowed, p.part_number, row_rev):
            continue
        rows.append(_part_file_overview_row(pf))

    for ef in (
        PartExtraFile.objects(part_number__iexact=p.part_number)
        .only(
            "part_number",
            "revision",
            "original_name",
            "rel_path",
            "size",
            "mime",
            "label",
            "uploaded_by",
            "uploaded_at",
            "source",
        )
        .order_by("revision", "-uploaded_at", "original_name")
    ):
        row_rev = _clean_rev_value(ef.revision or "")
        if isinstance(allowed, set) and not part_is_allowed(allowed, p.part_number, row_rev):
            continue
        rows.append(_extra_file_overview_row(ef))

    try:
        log_action(
            "part.files.view",
            resource_type="part",
            resource=f"{p.part_number}:{current_rev}",
        )
    except Exception:
        pass

    grouped = _group_file_overview_rows(rows, current_rev)
    return jsonify(
        {
            "part_number": p.part_number,
            "current_revision": grouped["current_revision"],
            "other_revisions": grouped["other_revisions"],
        }
    )


@bp.get("/parts/<pn>/insights")
@login_required
@require_items_view
def part_insights(pn):
    pn = (pn or "").strip()
    rev = request.args.get("rev")
    p = _find_part_doc(pn, rev)
    if not p:
        return jsonify({"error": "not found"}), 404

    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, p.part_number, p.revision or ""):
            return jsonify({"error": "forbidden"}), 403
    except Exception:
        pass

    attrs = harvest_part_attrs(p)
    norm_rev = _normalized_revision(p, attrs)
    meta = current_app.config.get("PROCESS_META", {})
    proc_list = normalize_process_list(attrs, list(p.processes or []), meta)
    classification = classify_part(attrs, list(p.processes or []), meta, category=p.category or "")
    missing = insights_missing_fields(attrs, p.description or "", list(p.processes or []), meta)
    deliverables_present = _deliverables_present(p.part_number, norm_rev)
    where_used_count, total_qty = _where_used_stats(p.part_number, norm_rev)
    has_bom = _has_bom_children(p.part_number, norm_rev)
    missing_recommended = recommended_deliverables(classification, deliverables_present, attrs, has_bom)

    return jsonify(
        {
            "part_number": p.part_number,
            "revision": norm_rev,
            "classification": classification,
            "processes_normalized": proc_list,
            "missing_fields": missing,
            "deliverables_present": deliverables_present,
            "deliverables_missing_recommended": missing_recommended,
            "where_used_count": where_used_count,
            "total_qty_used": total_qty,
        }
    )


@bp.post("/parts/<pn>/notes")
@login_required
@require_items_view
@csrf.exempt
def part_notes_update(pn):
    pn = (pn or "").strip()
    data = request.get_json(silent=True) or {}
    rev = data.get("rev") if "rev" in data else request.args.get("rev")
    notes = (data.get("notes") or "").strip()
    p = _find_part_doc(pn, rev)
    if not p:
        return jsonify({"ok": False, "error": "not found"}), 404
    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, p.part_number, p.revision or ""):
            return jsonify({"ok": False, "error": "forbidden"}), 403
    except Exception:
        pass
    try:
        migrate_legacy_annotations(p)
    except Exception:
        pass
    payload = set_part_notes(p, notes)
    try:
        log_action(
            "part.notes.update",
            resource_type="part",
            resource=f"{p.part_number}:{p.revision or ''}",
            meta={"notes_len": len(notes)},
        )
    except Exception:
        pass
    return jsonify({"ok": True, "notes": str((payload or {}).get("notes") or notes)})


@bp.post("/parts/<pn>/comments")
@login_required
@require_items_view
@csrf.exempt
def part_comments_add(pn):
    pn = (pn or "").strip()
    data = request.get_json(silent=True) or {}
    rev = data.get("rev") if "rev" in data else request.args.get("rev")
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "missing text"}), 400
    p = _find_part_doc(pn, rev)
    if not p:
        return jsonify({"ok": False, "error": "not found"}), 404
    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, p.part_number, p.revision or ""):
            return jsonify({"ok": False, "error": "forbidden"}), 403
    except Exception:
        pass
    migrate_legacy_annotations(p)
    comment = add_part_comment(
        p,
        author=getattr(current_user, "email", "") or "",
        text=text,
        ts=datetime.utcnow().isoformat(),
    )
    try:
        log_action(
            "part.comments.add",
            resource_type="part",
            resource=f"{p.part_number}:{p.revision or ''}",
            meta={"comment_len": len(text)},
        )
    except Exception:
        pass
    return jsonify({"ok": True, "comment": _comment_payload(comment)})


@bp.post("/parts/<pn>/refresh_files")
@login_required
@permissions_required("items.edit")
@csrf.exempt
def part_refresh_files(pn):
    pn = (pn or "").strip()
    data = request.get_json(silent=True) or {}
    rev_in = data.get("rev") if "rev" in data else request.args.get("rev")
    recursive_in = data.get("recursive") if "recursive" in data else request.args.get("recursive")
    rev_clean = _clean_rev_input(rev_in)
    p = _find_part_doc(pn, rev_clean)
    if not p:
        return jsonify({"ok": False, "error": "not found"}), 404
    target_rev = _clean_rev_value(p.revision or "")

    def _parse_bool(v: object) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        return str(v).strip().lower() in ("1", "true", "yes", "on")

    recursive = _parse_bool(recursive_in)

    pairs: list[tuple[str, str]] = [(p.part_number, target_rev)]
    if recursive:
        visited: set[tuple[str, str]] = set()
        queue: list[tuple[str, str]] = [(p.part_number, target_rev)]
        max_nodes = 5000
        while queue and len(visited) < max_nodes:
            parent_pn, parent_rev = queue.pop(0)
            key = (parent_pn, parent_rev)
            if key in visited:
                continue
            visited.add(key)
            for link in BOMLink.objects(parent_pn__iexact=parent_pn, parent_rev__iexact=parent_rev).only(
                "child_pn", "child_rev"
            ):
                cpn = (getattr(link, "child_pn", "") or "").strip()
                crev = _clean_rev_value(getattr(link, "child_rev", "") or "")
                if not cpn:
                    continue
                ckey = (cpn, crev)
                if ckey in visited:
                    continue
                queue.append(ckey)
        pairs = list(visited) if visited else pairs

    files_found_total = 0
    upserts_total = 0
    refreshed: list[dict] = []
    for pn_i, rev_i in pairs:
        found = discover_part_files(pn_i, rev_i)
        recs = []
        for (group, is_dwg), meta in (found or {}).items():
            rec = dict(meta)
            rec["ext_group"] = group
            rec["is_dwg"] = bool(is_dwg)
            recs.append(rec)
        files_found_total += len(recs)
        upserts_total += upsert_part_files(recs, pn_i, rev_i)
        refreshed.append({"pn": pn_i, "rev": rev_i, "files_found": len(recs)})

    thumbs = generate_thumbs_for_parts(pairs)
    try:
        log_action(
            "part.files.refresh",
            resource_type="part",
            resource=f"{p.part_number}:{target_rev}",
            meta={"recursive": recursive, "parts": len(pairs), "found": files_found_total, "upserts": upserts_total, "thumbs": thumbs},
        )
    except Exception:
        pass
    return jsonify(
        {
            "ok": True,
            "part_number": p.part_number,
            "revision": target_rev,
            "recursive": recursive,
            "parts_refreshed": len(pairs),
            "files_found": files_found_total,
            "artifacts_upserted": upserts_total,
            "thumbnails_generated": thumbs,
            "refreshed": refreshed[:200],
        }
    )


@bp.post("/part_delete")
@login_required
@permissions_required("items.edit")
@csrf.exempt
def part_delete():
    body = request.get_json(force=True, silent=True) or {}
    pn = (body.get("pn") or request.form.get("pn") or "").strip()
    if not pn:
        return jsonify({"ok": False, "error": "missing pn"}), 400
    rev = body.get("rev") if "rev" in body else request.form.get("rev")
    if rev is None:
        rev = ""
    rev = (rev or "").strip()
    target = Part.objects(part_number__iexact=pn, revision__iexact=rev).first()
    if not target and rev:
        for cand in Part.objects(part_number__iexact=pn):
            attrs = harvest_part_attrs(cand)
            if _normalized_revision(cand, attrs).lower() == rev.lower():
                target = cand
                rev = (cand.revision or "").strip()
                break
    if not target:
        return jsonify({"ok": False, "error": "not found"}), 404

    delete_children = _parse_bool(body.get("delete_children") or request.form.get("delete_children"))
    result = delete_part_and_refs_cascade(pn, rev, delete_children=delete_children)
    try:
        log_action(
            "part.delete",
            resource_type="part",
            resource=f"{pn}:{rev}",
            meta={"delete_children": bool(delete_children)},
        )
    except Exception:
        pass
    return jsonify({"ok": True, **result})
