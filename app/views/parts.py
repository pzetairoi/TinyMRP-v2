# app/views/parts.py
from flask import Blueprint, request, jsonify, current_app, send_file
from typing import Any, Optional
from datetime import datetime, timedelta
from flask_login import login_required, current_user
from mongoengine.queryset.visitor import Q
from io import BytesIO
import re
import os
from urllib.parse import urlsplit

from app.models.part import Part
from app.models.job import Job
from app.models.order import Order
from app.models.bom import BOMLink
from app.extensions import csrf
from app.services.thumbs import thumb_urls_for, thumb_urls_map
from app.services.attrs import approval_field_values, approval_filter_raw, approved_value, harvest_part_attrs
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
from app.services.filescan import (
    datasheet_attr_present,
    datasheet_url_from_attrs,
    discover_part_files,
    remove_stale_part_files,
    upsert_part_files,
)
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
from app.services.timezone_utils import format_display_ts, local_input_value, utc_iso, utc_now
from app.services.field_config import (
    boolean_filter_value,
    context_field_ids,
    date_filter_value,
    effective_source_paths,
    ensure_active_part_field_indexes,
    field_requires_runtime_scan,
    file_field_group,
    field_uses_materialized_value,
    field_index as field_config_index,
    get_field_config,
    mongo_field_from_source,
    matches_field_filter_constraints,
    number_filter_value,
    primary_query_path,
    query_paths_for_field,
    resolve_part_field_values,
    serialize_field_values,
)
from app.services.part_materialized import batch_file_groups_for_parts
from app.services.part_query import (
    filter_constraints,
    filter_value,
    or_contains,
    pairs_query,
    terms,
)
from app.services.arena_export import build_arena_bom_csv, build_arena_file_links_csv
from app.services.parts_delete import delete_part_and_refs_cascade
from app.services.part_norm import clean_rev, clean_rev_or_none
from app.services.part_annotations import (
    COMMENT_PRIORITIES,
    add_part_comment,
    annotation_payload,
    filtered_part_attrs,
    migrate_legacy_annotations,
    remove_part_comment,
    set_part_notes,
)
from app.services.notifications import create_notifications, notify_part_activity, part_url
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
    part = _find_part_doc(pn, rev_clean)
    attrs = harvest_part_attrs(part) if part else {}
    if datasheet_attr_present(attrs):
        groups.add("datasheet")
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
    ts_text = str(item.get("ts") or "").strip()
    ts_dt = None
    if ts_text:
        try:
            normalized = ts_text[:-1] + "+00:00" if ts_text.endswith("Z") else ts_text
            ts_dt = datetime.fromisoformat(normalized)
        except Exception:
            ts_dt = None
    if author:
        if resolved is not None:
            profile = resolved.get(author.lower()) or resolve_identity_profile(author)
        else:
            profile = resolve_identity_profile(author)
    priority = str(item.get("priority") or "").strip().lower()
    return {
        "id": str(item.get("id") or ""),
        "ts": utc_iso(ts_dt) or ts_text,
        "ts_display": format_display_ts(ts_dt, fmt="%Y-%m-%d %H:%M:%S %Z") or None,
        "ts_local": local_input_value(ts_dt) or None,
        "author": author,
        "author_display": (profile or {}).get("label") or author or "User",
        "author_profile": profile or resolve_identity_profile(author),
        "text": str(item.get("text") or ""),
        "priority": priority if priority in COMMENT_PRIORITIES else "",
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
        "recorded_at": utc_iso(recorded_at) or "",
        "recorded_at_display": format_display_ts(recorded_at, fmt="%Y-%m-%d %H:%M:%S %Z") or "",
        "recorded_at_local": local_input_value(recorded_at) or "",
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
        "recorded_at": utc_iso(ef.uploaded_at) or "",
        "recorded_at_display": format_display_ts(ef.uploaded_at, fmt="%Y-%m-%d %H:%M:%S %Z") or "",
        "recorded_at_local": local_input_value(ef.uploaded_at) or "",
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


@login_required
@require_items_view
@bp.route("/parts_lazy", methods=["GET", "POST"])
@csrf.exempt
def parts_lazy():
    body = request.get_json(force=True, silent=True) or {}
    try:
        first = max(0, int(body.get("first", 0)))
    except (TypeError, ValueError):
        first = 0
    try:
        requested_rows = int(body.get("rows", 25))
    except (TypeError, ValueError):
        requested_rows = 25
    rows = min(requested_rows, 100) if requested_rows > 0 else 25
    sort_field = body.get("sortField") or "part_number"
    sort_order = int(body.get("sortOrder", 1))
    filters = body.get("filters", {}) or {}

    field_config = get_field_config()
    ensure_active_part_field_indexes(field_config)
    parts_context_ids = context_field_ids("parts_list", field_config)
    field_meta = field_config_index(field_config)
    runtime_filter_ids = {field_id for field_id in parts_context_ids if field_requires_runtime_scan(field_id, field_config)}
    materialized_filter_ids = {field_id for field_id in parts_context_ids if field_uses_materialized_value(field_id, field_config)}
    sortable_ids = {field_id for field_id in parts_context_ids if field_meta.get(field_id, {}).get("sortable")}
    filterable_ids = {field_id for field_id in parts_context_ids if field_meta.get(field_id, {}).get("filterable")}

    if sort_field not in sortable_ids:
        sort_field = "part_number"
    runtime_sort = field_requires_runtime_scan(sort_field, field_config)
    mapped_sort = None if runtime_sort else primary_query_path(sort_field, field_config)
    if not runtime_sort and not mapped_sort:
        sort_field = "part_number"
        mapped_sort = primary_query_path(sort_field, field_config) or "part_number"
    order_by = f"-{mapped_sort}" if mapped_sort and sort_order == -1 else (mapped_sort or "part_number")
    order_fields = [order_by]
    if mapped_sort != "part_number":
        order_fields.append("part_number")
    if mapped_sort != "revision":
        order_fields.append("revision")

    def _mongo_path(path: str) -> str:
        return str(path or "").replace("__", ".")

    def _field_false_or_missing_q(path: str) -> Q:
        return Q(**{path: False}) | Q(__raw__={_mongo_path(path): {"$exists": False}})

    def _default_match_mode(data_type: str) -> str:
        if data_type == "boolean":
            return "equals"
        if data_type == "number":
            return "equals"
        if data_type == "date":
            return "dateIs"
        return "contains"

    def _combine_q(items: list[Q], operator: str) -> Q:
        if not items:
            return Q()
        combined = items[0]
        for item in items[1:]:
            combined = (combined | item) if operator == "or" else (combined & item)
        return combined

    def _path_empty_q(path: str) -> Q:
        mongo_path = _mongo_path(path)
        return Q(__raw__={"$or": [{mongo_path: {"$exists": False}}, {mongo_path: None}, {mongo_path: ""}]})

    def _path_not_empty_q(path: str) -> Q:
        mongo_path = _mongo_path(path)
        return Q(__raw__={mongo_path: {"$exists": True, "$nin": [None, ""]}})

    def _text_constraint_q(paths: list[str], match_mode: str, value: Any) -> Q:
        text = str(value or "").strip()
        if match_mode == "contains":
            term_queries = [
                _combine_q([Q(**{f"{path}__icontains": term}) for path in paths], "or")
                for term in terms(text)
            ]
            return _combine_q(term_queries, "and")
        lookups = {
            "startsWith": "istartswith",
            "endsWith": "iendswith",
            "equals": "iexact",
        }
        if match_mode in lookups:
            lookup = lookups[match_mode]
            return _combine_q([Q(**{f"{path}__{lookup}": text}) for path in paths], "or")
        if match_mode == "notContains":
            return _combine_q([~Q(**{f"{path}__icontains": text}) for path in paths], "and")
        if match_mode == "notEquals":
            return _combine_q([~Q(**{f"{path}__iexact": text}) for path in paths], "and")
        return _text_constraint_q(paths, "contains", text)

    def _typed_constraint_q(paths: list[str], data_type: str, constraint: dict[str, Any]) -> Q:
        match_mode = str(constraint.get("match_mode") or _default_match_mode(data_type))
        value = constraint.get("value")
        if match_mode == "isEmpty":
            return _combine_q([_path_empty_q(path) for path in paths], "and")
        if match_mode == "isNotEmpty":
            return _combine_q([_path_not_empty_q(path) for path in paths], "or")
        if data_type in {"text", "link"}:
            return _text_constraint_q(paths, match_mode, value)
        if data_type == "boolean":
            expected = boolean_filter_value(value)
            if expected is None:
                return Q()
            if match_mode == "notEquals":
                expected = not expected
            return _combine_q([Q(**{path: expected}) for path in paths], "or")
        if data_type == "number":
            parsed = number_filter_value(value)
            if match_mode == "between" and isinstance(value, (list, tuple)) and len(value) >= 2:
                left = number_filter_value(value[0])
                right = number_filter_value(value[1])
                if left and right:
                    low = min(left[1], right[1])
                    high = max(left[1], right[1])
                    return _combine_q([Q(**{f"{path}__gte": low, f"{path}__lte": high}) for path in paths], "or")
            if parsed is None:
                return Q()
            if match_mode == "equals" and parsed[0] != "=":
                op, start, end = parsed
                if op == "range":
                    return _combine_q([Q(**{f"{path}__gte": start, f"{path}__lte": end}) for path in paths], "or")
                suffix = {">": "gt", ">=": "gte", "<": "lt", "<=": "lte"}.get(op, "")
                return _combine_q([Q(**{f"{path}__{suffix}" if suffix else path: start}) for path in paths], "or")
            mode_ops = {"equals": "", "notEquals": "ne", "lt": "lt", "lte": "lte", "gt": "gt", "gte": "gte"}
            if match_mode in mode_ops:
                suffix = mode_ops[match_mode]
                return _combine_q([Q(**{f"{path}__{suffix}" if suffix else path: parsed[1]}) for path in paths], "or")
            op, start, end = parsed
            if op == "range":
                return _combine_q([Q(**{f"{path}__gte": start, f"{path}__lte": end}) for path in paths], "or")
            suffix = {">": "gt", ">=": "gte", "<": "lt", "<=": "lte"}.get(op, "")
            return _combine_q([Q(**{f"{path}__{suffix}" if suffix else path: start}) for path in paths], "or")
        if data_type == "date":
            target = date_filter_value(value)
            if target is None:
                return Q()
            start = target.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            if match_mode == "dateBefore":
                return _combine_q([Q(**{f"{path}__lt": start}) for path in paths], "or")
            if match_mode == "dateAfter":
                return _combine_q([Q(**{f"{path}__gte": end}) for path in paths], "or")
            day_queries = [Q(**{f"{path}__gte": start, f"{path}__lt": end}) for path in paths]
            matched = _combine_q(day_queries, "or")
            return ~matched if match_mode == "dateIsNot" else matched
        return Q()

    def _field_constraints_q(field_id: str, data_type: str, operator: str, constraints: list[dict[str, Any]]) -> Q | None:
        if field_id == "approved":
            queries = []
            for constraint in constraints:
                mode = str(constraint.get("match_mode") or "equals")
                expected = boolean_filter_value(constraint.get("value"))
                if mode == "isEmpty":
                    expected = False
                elif mode == "isNotEmpty":
                    expected = True
                elif mode == "notEquals" and expected is not None:
                    expected = not expected
                if expected is not None:
                    queries.append(_approval_q(expected))
            return _combine_q(queries, operator) if queries else None
        if file_field_group(field_id):
            queries = []
            for constraint in constraints:
                mode = str(constraint.get("match_mode") or "equals")
                expected = boolean_filter_value(constraint.get("value"))
                if mode == "isEmpty":
                    expected = False
                elif mode == "isNotEmpty":
                    expected = True
                elif mode == "notEquals" and expected is not None:
                    expected = not expected
                if expected is not None:
                    queries.append(_file_filter_q(field_id, expected))
            return _combine_q(queries, operator) if queries else None
        paths = query_paths_for_field(field_id, field_config)
        if field_id == "process":
            queries = []
            for constraint in constraints:
                mode = str(constraint.get("match_mode") or "contains")
                if mode == "contains":
                    queries.append(_process_filter_q(str(constraint.get("value") or "")))
                else:
                    process_paths = ["processes", "attrs__process", "attrs__process2", "attrs__process3", "attrs__processes", "canonical__processes"]
                    queries.append(_typed_constraint_q(process_paths, data_type, constraint))
            return _combine_q(queries, operator)
        if not paths:
            return None
        return _combine_q([_typed_constraint_q(paths, data_type, item) for item in constraints], operator)

    def _or_array_regex(field: str, term: str) -> Q:
        if not term:
            return Q()
        return Q(__raw__={field: {"$regex": re.escape(term), "$options": "i"}})

    process_meta = current_app.config.get("PROCESS_META", {}) or {}

    def _process_filter_q(text: str) -> Q:
        raw_text = str(text or "").strip()
        if not raw_text:
            return Q()
        normalized = normalize_processes({"processes": [raw_text]}, process_meta)
        raw_terms = terms(raw_text)
        if raw_text.lower() not in raw_terms:
            raw_terms.insert(0, raw_text.lower())
        out = Q(processes__in=normalized) if normalized else Q()
        for term in raw_terms:
            out = (
                out
                | _or_array_regex("processes", term)
                | Q(attrs__process__icontains=term)
                | Q(attrs__process2__icontains=term)
                | Q(attrs__process3__icontains=term)
                | Q(attrs__processes__icontains=term)
                | Q(canonical__processes__icontains=term)
            )
        category_paths = query_paths_for_field("category", field_config) or ["attrs__category", "category"]
        material_paths = query_paths_for_field("material", field_config) or ["attrs__material"]
        normalized_text = raw_text.lower()
        if normalized_text in {"hardware", "fastener", "fasteners"}:
            out = out | or_contains(category_paths, "hardware")
        elif normalized_text in {"sheet metal", "sheetmetal", "sheet"}:
            out = out | or_contains(category_paths, "sheet") | or_contains(material_paths, "sheet")
        return out

    def _file_filter_q(field_id: str, expected: bool) -> Q:
        path = primary_query_path(field_id, field_config) or field_id
        return Q(**{path: True}) if expected else _field_false_or_missing_q(path)

    def _approval_q(expected: bool) -> Q:
        raw = approval_filter_raw(approved=expected)
        return Q(__raw__=raw)

    q = Q()
    fallback_base_q = Q()
    typed_filter_specs: list[tuple[str, str, str, list[dict[str, Any]]]] = []
    runtime_filter_specs: list[tuple[str, str, str, list[dict[str, Any]]]] = []
    materialized_filter_specs: list[tuple[str, str, str, list[dict[str, Any]]]] = []
    for field_id in filterable_ids:
        data_type = str(field_meta.get(field_id, {}).get("data_type") or "text")
        if data_type == "image":
            continue
        operator, constraints = filter_constraints(
            filters,
            field_id,
            default_match_mode=_default_match_mode(data_type),
        )
        if not constraints:
            continue
        spec = (field_id, data_type, operator, constraints)
        if field_id in runtime_filter_ids:
            runtime_filter_specs.append(spec)
            continue
        field_q = _field_constraints_q(field_id, data_type, operator, constraints)
        if field_q is None:
            typed_filter_specs.append(spec)
            continue
        q = q & field_q
        if field_id in materialized_filter_ids:
            # Keep the unfiltered base query for old rows that have not yet had
            # this materialized field rebuilt.
            materialized_filter_specs.append(spec)
        else:
            fallback_base_q = fallback_base_q & field_q

    global_value = filter_value(filters, "global", "")
    if global_value:
        global_paths: list[str] = []

        def _append_search_path(path: str | None) -> None:
            if path and path not in global_paths:
                global_paths.append(path)

        for field_id, fallback_path in (
            ("part_number", "part_number"),
            ("description", "description"),
            ("notes", "notes_search"),
            ("comments", "comments_search"),
        ):
            for path in query_paths_for_field(field_id, field_config):
                _append_search_path(path)
            for source_path in effective_source_paths(field_id, field_config):
                _append_search_path(mongo_field_from_source(source_path))
            _append_search_path(fallback_path)

        for term in terms(global_value):
            or_q = Q()
            for path in global_paths:
                or_q = or_q | Q(**{f"{path}__icontains": term})
            q = q & or_q
            fallback_base_q = fallback_base_q & or_q

    job_id = body.get("job") or request.args.get("job")
    job_filter_enabled = bool(job_id) and str(body.get("job_only", "true")).lower() != "false"
    if job_filter_enabled and job_id:
        job = Job.objects(id=job_id).first()
        if job and job.bom:
            pairs = {
                ((line.pn or "").strip(), _clean_rev_value(line.rev))
                for line in (job.bom or [])
                if (line.pn or "").strip()
            }
            if pairs:
                q = q & pairs_query(pairs)
                fallback_base_q = fallback_base_q & pairs_query(pairs)

    allowed_scope = allowed_parts_for(current_user)
    if isinstance(allowed_scope, set):
        if not allowed_scope:
            return jsonify({"data": [], "totalRecords": 0})
        allowed_q = Q()
        for pn, rev in allowed_scope:
            pn_clean = str(pn or "").strip()
            if not pn_clean:
                continue
            if rev:
                allowed_q = allowed_q | Q(part_number__iexact=pn_clean, revision__iexact=rev)
            else:
                allowed_q = allowed_q | Q(part_number__iexact=pn_clean)
        q = q & allowed_q
        fallback_base_q = fallback_base_q & allowed_q

    qs = Part.objects(q)
    fallback_qs = Part.objects(fallback_base_q)

    def _missing_materialized_q(field_ids: set[str]) -> Q:
        out = Q()
        for field_id in field_ids:
            out = out | Q(__raw__={f"field_values.{field_id}": {"$exists": False}})
        return out

    def _sort_value(values: dict[str, Any], part: Part, rev: str, data_type: str):
        value = values.get(sort_field)
        if data_type == "number":
            try:
                return float(value)
            except Exception:
                return float("-inf") if sort_order == -1 else float("inf")
        if data_type == "boolean":
            return 1 if bool(value) else 0
        if sort_field == "part_number":
            return str(getattr(part, "part_number", "") or "").lower()
        if sort_field == "revision":
            return str(values.get("revision", rev) or rev or "").lower()
        return str(value or "").lower()

    def _coverage_map(parts_list: list[Part]) -> dict[tuple[str, str], set[str]]:
        return batch_file_groups_for_parts(parts_list)

    needs_scan = any(
        [
            bool(typed_filter_specs),
            bool(runtime_filter_specs),
            runtime_sort,
        ]
    )

    if needs_scan:
        scan_order_by = order_by if not runtime_sort else "part_number"
        all_docs = list(qs.order_by(scan_order_by, "part_number", "revision").only("part_number", "revision", "description", "category", "attrs", "processes"))
        scan_requires_values = bool(runtime_sort or typed_filter_specs or runtime_filter_specs)
        coverage = _coverage_map(all_docs) if scan_requires_values else {}
        filtered_docs: list[Part] = []
        resolved_cache: dict[tuple[str, str], dict[str, Any]] = {}
        for part in all_docs:
            attrs = harvest_part_attrs(part)
            rev = _normalized_revision(part, attrs)
            groups = coverage.get((part.part_number, rev)) or set()
            values: dict[str, Any] = {}
            if scan_requires_values:
                values = resolve_part_field_values(
                    part,
                    parts_context_ids,
                    attrs=attrs,
                    config=field_config,
                    extra={"part_number": part.part_number, "revision": rev},
                    coverage=groups,
                )
            if any(
                not matches_field_filter_constraints(values.get(field_id), constraints, operator, data_type)
                for field_id, data_type, operator, constraints in typed_filter_specs
            ):
                continue
            if any(
                not matches_field_filter_constraints(values.get(field_id), constraints, operator, data_type)
                for field_id, data_type, operator, constraints in runtime_filter_specs
            ):
                continue
            if values:
                resolved_cache[(part.part_number, rev)] = values
            filtered_docs.append(part)
        if runtime_sort:
            sort_type = str((field_meta.get(sort_field) or {}).get("data_type") or "text")
            reverse = sort_order == -1

            def _runtime_sort_key(doc: Part):
                attrs = harvest_part_attrs(doc)
                rev = _normalized_revision(doc, attrs)
                value = (resolved_cache.get((doc.part_number, rev)) or {}).get(sort_field)
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
            qs.order_by(*order_fields)
            .only(
                "part_number", "revision", "description", "category", "attrs", "processes",
                "file_groups", "field_values", "has_pdf", "has_png", "has_dxf", "has_step",
                "has_edr", "has_3mf", "has_ply", "has_stl", "has_datasheet",
            )
            .skip(first)
            .limit(rows)
        )
        coverage = {}
        resolved_cache = {}

        fallback_limit = max(first + rows, rows)
        if materialized_filter_specs and filtered < fallback_limit:
            stale_filter_ids = {field_id for field_id, _data_type, _operator, _constraints in materialized_filter_specs}
            stale_candidates_qs = fallback_qs.filter(_missing_materialized_q(stale_filter_ids))
            stale_candidates = list(
                stale_candidates_qs.only(
                    "part_number", "revision", "description", "category", "attrs", "processes",
                    "file_groups", "field_values", "has_pdf", "has_png", "has_dxf", "has_step",
                    "has_edr", "has_3mf", "has_ply", "has_stl", "has_datasheet",
                )
            )
            fallback_docs: list[Part] = []
            fallback_values_cache: dict[tuple[str, str], dict[str, Any]] = {}
            fallback_sort_type = str((field_meta.get(sort_field) or {}).get("data_type") or "text")
            fallback_field_ids = {field_id for field_id, _data_type, _operator, _constraints in materialized_filter_specs}
            if sort_field:
                fallback_field_ids.add(sort_field)
            fallback_field_ids.update({"part_number", "revision"})

            for part in stale_candidates:
                attrs = harvest_part_attrs(part)
                rev = _normalized_revision(part, attrs)
                values = resolve_part_field_values(
                    part,
                    fallback_field_ids,
                    attrs=attrs,
                    config=field_config,
                    extra={"part_number": part.part_number, "revision": rev},
                )
                if any(
                    not matches_field_filter_constraints(values.get(field_id), constraints, operator, data_type)
                    for field_id, data_type, operator, constraints in materialized_filter_specs
                ):
                    continue
                fallback_values_cache[(part.part_number, rev)] = values
                fallback_docs.append(part)

            if fallback_docs:
                db_prefix = list(
                    qs.order_by(*order_fields)
                    .only(
                        "part_number", "revision", "description", "category", "attrs", "processes",
                        "file_groups", "field_values", "has_pdf", "has_png", "has_dxf", "has_step",
                        "has_edr", "has_3mf", "has_ply", "has_stl", "has_datasheet",
                    )
                    .limit(fallback_limit)
                )
                combined = db_prefix + fallback_docs
                combined_sort_values = dict(fallback_values_cache)
                for part in db_prefix:
                    attrs = harvest_part_attrs(part)
                    rev = _normalized_revision(part, attrs)
                    key = (part.part_number, rev)
                    if key in combined_sort_values:
                        continue
                    combined_sort_values[key] = resolve_part_field_values(
                        part,
                        fallback_field_ids,
                        attrs=attrs,
                        config=field_config,
                        extra={"part_number": part.part_number, "revision": rev},
                    )
                combined.sort(
                    key=lambda part: (
                        _sort_value(
                            combined_sort_values.get(
                                (
                                    part.part_number,
                                    _normalized_revision(part, harvest_part_attrs(part)),
                                ),
                                {},
                            ),
                            part,
                            _normalized_revision(part, harvest_part_attrs(part)),
                            fallback_sort_type,
                        ),
                        str(getattr(part, "part_number", "") or "").lower(),
                        str(_normalized_revision(part, harvest_part_attrs(part)) or "").lower(),
                    ),
                    reverse=sort_order == -1,
                )
                filtered += len(fallback_docs)
                docs = combined[first:first + rows]
                coverage = {}

    thumb_map = thumb_urls_map([(part.part_number, _normalized_revision(part, harvest_part_attrs(part))) for part in docs])

    out = []
    for part in docs:
        attrs = harvest_part_attrs(part)
        pn = part.part_number
        rev = _normalized_revision(part, attrs)
        groups = coverage.get((pn, rev)) or set()
        process_list = normalize_process_list(attrs, list(part.processes or []), current_app.config.get("PROCESS_META", {}))
        thumb_list = thumb_map.get((pn, rev)) or []
        values = dict(resolved_cache.get((pn, rev)) or {})
        if not values:
            values = resolve_part_field_values(
                part,
                parts_context_ids,
                attrs=attrs,
                config=field_config,
                extra={"part_number": pn, "revision": rev, "thumbnail": thumb_list[0] if thumb_list else ""},
                coverage=groups,
            )
        elif thumb_list:
            values["thumbnail"] = thumb_list[0]
        values["display_code"] = f"{pn}-{rev}" if rev else pn
        values = serialize_field_values(values, field_config)
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
                "has_pdf": bool(values.get("has_pdf", getattr(part, "has_pdf", False))),
                "has_png": bool(values.get("has_png", getattr(part, "has_png", False))),
                "has_dxf": bool(values.get("has_dxf", getattr(part, "has_dxf", False))),
                "has_step": bool(values.get("has_step", getattr(part, "has_step", False))),
                "has_edr": bool(values.get("has_edr", getattr(part, "has_edr", False))),
                "has_3mf": bool(values.get("has_3mf", getattr(part, "has_3mf", False))),
                "has_ply": bool(values.get("has_ply", getattr(part, "has_ply", False))),
                "has_stl": bool(values.get("has_stl", getattr(part, "has_stl", False))),
                "has_datasheet": bool(values.get("has_datasheet", getattr(part, "has_datasheet", False))),
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

    def datasheet_file_url(f: PartFile):
        return file_url_for(f, kind="preview")

    def file_label(f: PartFile) -> str:
        name = os.path.basename(f.rel_path or f.path or "")
        return name or "file"

    files = {"pdf": [], "dxf": [], "step": [], "edr": [], "3mf": [], "ply": [], "stl": [], "datasheet": []}
    for f in (
        PartFile.objects(part_number__iexact=p.part_number, revision__iexact=norm_rev)
        .only("ext_group", "rel_path", "path", "http_url")
        .order_by("ext_group", "rel_path")
    ):
        if f.ext_group in files:
            files[f.ext_group].append(
                {
                    "url": datasheet_file_url(f) if f.ext_group == "datasheet" else to_url(f),
                    "rel": f.rel_path or "",
                    "name": file_label(f),
                }
            )
    datasheet_url = datasheet_url_from_attrs(attrs)
    if datasheet_url:
        datasheet_name = os.path.basename(urlsplit(datasheet_url).path) or "datasheet"
        files["datasheet"].append({"url": datasheet_url, "rel": "", "name": datasheet_name})
    datasheet_summary_url = files["datasheet"][0]["url"] if files["datasheet"] else ""
    _, _, summary_field_values = _context_field_values(
        p,
        "part_detail_summary",
        extra={"part_number": p.part_number, "revision": norm_rev, "datasheet": datasheet_summary_url},
    )
    summary_field_values.update(approval_field_values(attrs))
    summary_field_values = serialize_field_values(summary_field_values)

    uploader_identity = _attr_identity(attrs, "uploader", "uploaded_by", "uploadedby", "author", "drawnby")
    approver_identity = str(approved_value(attrs) or "").strip()
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
    priority = str(data.get("priority") or "").strip().lower()
    comment = add_part_comment(
        p,
        author=getattr(current_user, "email", "") or "",
        text=text,
        ts=utc_iso(utc_now()),
        priority=priority if priority in COMMENT_PRIORITIES else None,
    )
    try:
        log_action(
            "part.comments.add",
            resource_type="part",
            resource=f"{p.part_number}:{p.revision or ''}",
            meta={"comment_len": len(text), "priority": comment.get("priority") or ""},
        )
    except Exception:
        pass
    try:
        notify_part_activity(
            p,
            actor_email=getattr(current_user, "email", "") or "",
            text=text,
            title=f"New comment on {p.part_number}",
            comment_id=str(comment.get("id") or ""),
        )
    except Exception:
        pass
    return jsonify({"ok": True, "comment": _comment_payload(comment)})


@bp.post("/parts/<pn>/comments/delete")
@login_required
@require_items_view
@csrf.exempt
def part_comments_delete(pn):
    pn = (pn or "").strip()
    data = request.get_json(silent=True) or {}
    rev = data.get("rev") if "rev" in data else request.args.get("rev")
    comment_id = str(data.get("id") or "").strip()
    ts = str(data.get("ts") or "").strip()
    text = str(data.get("text") or "").strip()
    if not comment_id and not ts:
        return jsonify({"ok": False, "error": "missing id or ts"}), 400
    p = _find_part_doc(pn, rev)
    if not p:
        return jsonify({"ok": False, "error": "not found"}), 404
    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, p.part_number, p.revision or ""):
            return jsonify({"ok": False, "error": "forbidden"}), 403
    except Exception:
        pass
    removed = remove_part_comment(p, comment_id=comment_id or None, ts=ts or None, text=text or None)
    if removed is None:
        return jsonify({"ok": False, "error": "comment not found"}), 404
    try:
        log_action(
            "part.comments.delete",
            resource_type="part",
            resource=f"{p.part_number}:{p.revision or ''}",
            meta={"comment_len": len(str(removed.get("text") or ""))},
        )
    except Exception:
        pass
    try:
        create_notifications(
            recipient_emails=[str(removed.get("author") or "")],
            actor_email=getattr(current_user, "email", "") or "",
            kind="comment_changed",
            title=f"Your comment on {p.part_number} was removed",
            body=str(removed.get("text") or ""),
            url=part_url(p.part_number, p.revision or ""),
            part_number=p.part_number,
            revision=p.revision or "",
            comment_id=str(removed.get("id") or ""),
        )
    except Exception:
        pass
    payload = annotation_payload(p)
    comments = [_comment_payload(row) for row in (payload.get("comments") or [])]
    return jsonify({"ok": True, "comments": comments})


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
    removed_total = 0
    refreshed: list[dict] = []
    for pn_i, rev_i in pairs:
        part_doc = (
            p
            if p.part_number.lower() == pn_i.lower() and _clean_rev_value(p.revision or "") == _clean_rev_value(rev_i)
            else Part.objects(part_number__iexact=pn_i, revision__iexact=rev_i)
            .only("attrs", "canonical", "description", "revision", "category", "uom")
            .first()
        )
        part_attrs = harvest_part_attrs(part_doc) if part_doc else {}
        found = discover_part_files(
            pn_i,
            rev_i,
            approved=bool(approved_value(part_attrs)) if part_doc else None,
            attrs=part_attrs,
        )
        recs = []
        for (group, is_dwg), meta in (found or {}).items():
            rec = dict(meta)
            rec["ext_group"] = group
            rec["is_dwg"] = bool(is_dwg)
            recs.append(rec)
        files_found_total += len(recs)
        upserts_total += upsert_part_files(recs, pn_i, rev_i)
        try:
            removed_report = remove_stale_part_files(pn_i, rev_i, found)
        except Exception:
            removed_report = {"count": 0}
        removed_count = int(removed_report.get("count") or 0)
        removed_total += removed_count
        refreshed.append({"pn": pn_i, "rev": rev_i, "files_found": len(recs), "files_removed": removed_count})

    thumbs = generate_thumbs_for_parts(pairs)
    try:
        log_action(
            "part.files.refresh",
            resource_type="part",
            resource=f"{p.part_number}:{target_rev}",
            meta={"recursive": recursive, "parts": len(pairs), "found": files_found_total, "upserts": upserts_total, "removed": removed_total, "thumbs": thumbs},
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
            "artifacts_removed": removed_total,
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
    delete_files = _parse_bool(body.get("delete_files") or request.form.get("delete_files"))
    result = delete_part_and_refs_cascade(pn, rev, delete_children=delete_children, delete_files=delete_files)
    try:
        log_action(
            "part.delete",
            resource_type="part",
            resource=f"{pn}:{rev}",
            meta={"delete_children": bool(delete_children), "delete_files": bool(delete_files)},
        )
    except Exception:
        pass
    return jsonify({"ok": True, **result})
