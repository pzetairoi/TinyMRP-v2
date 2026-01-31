# app/views/parts.py
from flask import Blueprint, request, jsonify, current_app
from typing import Optional
from datetime import datetime
from flask_login import login_required, current_user
from mongoengine.queryset.visitor import Q
import re
import os

from app.models.part import Part
from app.models.job import Job
from app.models.order import Order
from app.models.bom import BOMLink
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.extensions import csrf
from app.services.thumbs import thumb_urls_for, drawing_urls_for
from app.services.attrs import harvest_part_attrs, approved_value
from app.models.artifact import PartFile
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
from app.services.acl import require_items_view, allowed_parts_for, part_is_allowed, user_has_permission, permissions_required
from app.services.audit import log_action
from app.services.files_access import file_url_for, public_file_urls_enabled
from app.services.parts_delete import delete_part_and_refs
from app.services.part_norm import clean_rev, clean_rev_or_none

bp = Blueprint("parts_api", __name__, url_prefix="/api")

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


def _jobs_orders_summary(pn: str, rev: str | None, user) -> list[dict]:
    paths = _ancestor_paths(pn, rev)
    try:
        roles = {getattr(r, "name", "") for r in (user.roles or [])}
    except Exception:
        roles = set()
    is_customer_viewer = "customer_viewer" in roles
    is_supplier_viewer = "supplier_viewer" in roles
    is_admin = "admin" in roles
    can_jobs = is_admin or user_has_permission(user, "jobs.view")
    can_orders = is_admin or user_has_permission(user, "orders.view")

    job_q = Job.objects()
    if is_customer_viewer:
        cust_ids = [c.id for c in Customer.objects(users=user).only("id")]
        job_q = job_q.filter(customer__in=cust_ids) if cust_ids else Job.objects(id__in=[])
    if not can_jobs:
        job_q = Job.objects(id__in=[])

    order_q = Order.objects(status__ne="cancelled")
    if is_supplier_viewer:
        sup_ids = [s.id for s in Supplier.objects(users=user).only("id")]
        order_q = order_q.filter(supplier__in=sup_ids) if sup_ids else Order.objects(id__in=[])
    if not can_orders:
        order_q = Order.objects(id__in=[])

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


_EMPTY_VALUES = {"", "n/a", "na", "none", "null", "0", "false"}

def _is_blankish(value: object, *, allow_na: bool = False) -> bool:
    if value is None:
        return True
    text = str(value).strip().lower()
    if allow_na and text in ("n/a", "na"):
        return False
    return text in _EMPTY_VALUES

def _is_approved(attrs: dict) -> bool:
    raw = approved_value(attrs)
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text in _EMPTY_VALUES:
        return False
    return True

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

    sort_map = {
        "material": "attrs__material",
        "finish": "attrs__finish",
        "mass": "attrs__mass",
        "revision": "revision",
        "category": "category",
        "description": "description",
        "part_number": "part_number",
    }
    allowed = set(sort_map.keys())
    if sort_field not in allowed:
        sort_field = "part_number"
    mapped = sort_map.get(sort_field, sort_field)
    order_by = f"-{mapped}" if sort_order == -1 else mapped

    def _terms(s: str):
        return [t for t in re.split(r"\s+", (s or "").strip().lower()) if t]

    def add_filter(q: Q, key: str, *fields):
        f = filters.get(key) or {}
        val = (f.get("value") or "").strip()
        if not val or val.startswith("__"):
            return q
        for t in _terms(val):
            or_q = Q()
            for fld in fields:
                or_q = or_q | Q(**{f"{fld}__icontains": t})
            q = q & or_q
        return q

    def _flag_enabled(key: str) -> bool:
        val = (filters.get(key) or {}).get("value")
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        return str(val).strip().lower() in ("true", "1", "yes", "y", "on")

    q = Q()
    q = add_filter(q, "part_number", "part_number")
    q = add_filter(q, "revision", "revision")
    q = add_filter(q, "description", "description")
    q = add_filter(q, "category", "category")
    material_val = (filters.get("material") or {}).get("value")
    material_val_norm = str(material_val or "").strip().lower()
    if material_val_norm not in ("__missing__", "missing", "(missing)"):
        q = add_filter(q, "material", "attrs__material")
    q = add_filter(q, "finish", "attrs__finish")
    def _process_filter_q(terms: list[str]) -> Q:
        or_q = Q()
        if terms:
            or_q = or_q | Q(processes__in=terms)
            for t in terms:
                or_q = or_q | Q(attrs__process__icontains=t)
                or_q = or_q | Q(attrs__process2__icontains=t)
                or_q = or_q | Q(attrs__process3__icontains=t)
                or_q = or_q | Q(attrs__processes__icontains=t)
        return or_q

    proc_key = "process" if "process" in filters else "processes"
    proc_val = (filters.get(proc_key) or {}).get("value")
    proc_val_norm = str(proc_val or "").strip().lower()
    if proc_val_norm in ("hardware", "fastener", "fasteners"):
        q = q & (
            _process_filter_q(["hardware", "fastener", "fasteners"])
            | Q(attrs__category__icontains="hardware")
            | Q(category__icontains="hardware")
        )
    elif proc_val_norm in ("sheet metal", "sheetmetal", "sheet"):
        q = q & (
            _process_filter_q(["lasercut", "profile cut", "cutting", "folding", "rolling", "sheet"])
            | Q(attrs__category__icontains="sheet")
            | Q(category__icontains="sheet")
            | Q(attrs__material__icontains="sheet")
        )
    else:
        q = add_filter(q, proc_key, "processes", "attrs__process", "attrs__process2", "attrs__process3", "attrs__processes")
    g = (filters.get("global") or {}).get("value")
    if g:
        for t in _terms(str(g)):
            orq = (
                Q(part_number__icontains=t)
                | Q(revision__icontains=t)
                | Q(description__icontains=t)
                | Q(category__icontains=t)
                | Q(attrs__material__icontains=t)
                | Q(attrs__finish__icontains=t)
                | Q(processes__icontains=t)
            )
            q = q & orq

    def _pairs_q(pairs: set[tuple[str, str]]):
        pair_q = Q()
        for pn, rev in pairs:
            pn_clean = (pn or "").strip()
            if not pn_clean:
                continue
            rev_clean = _clean_rev_value(rev)
            pair_q = pair_q | Q(part_number__iexact=pn_clean, revision__iexact=rev_clean)
        return pair_q

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
    job_number_filter = str((filters.get("job_number") or {}).get("value") or "").strip()
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
    allowed = allowed_parts_for(current_user)
    if isinstance(allowed, set):
        if not allowed:
            return jsonify({"data": [], "totalRecords": 0})
        allowed_q = Q()
        for pn, rev in allowed:
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
        qs = qs.filter(
            __raw__={
                "$or": [
                    {"attrs.material": {"$exists": False}},
                    {"attrs.material": ""},
                    {"attrs.material": None},
                ]
            }
        )

    def _bool_filter(val: object) -> Optional[bool]:
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        s = str(val).strip().lower()
        if s in ("true", "1", "yes", "y"):
            return True
        if s in ("false", "0", "no", "n", "missing"):
            return False
        return None

    has_pdf_filter = _bool_filter((filters.get("has_pdf") or {}).get("value"))
    full_files_filter = _flag_enabled("full_files")
    approved_filter = _flag_enabled("approved")
    min_props_filter = _flag_enabled("min_props")

    def _coverage_map(parts_list: list[Part]) -> dict[tuple[str, str], set[str]]:
        if not parts_list:
            return {}
        pn_list = list({p.part_number for p in parts_list if p.part_number})
        rev_list = []
        for p in parts_list:
            attrs = harvest_part_attrs(p)
            rev_list.append(_normalized_revision(p, attrs))
        rev_list = list({r for r in rev_list})
        qf = PartFile.objects(part_number__in=pn_list)
        if rev_list:
            qf = qf.filter(revision__in=list(set(rev_list)))
        coverage: dict[tuple[str, str], set[str]] = {}
        for f in qf.only("part_number", "revision", "ext_group"):
            key = (f.part_number, f.revision or "")
            coverage.setdefault(key, set()).add((f.ext_group or "").lower())
        return coverage

    needs_scan = any([
        has_pdf_filter is not None,
        full_files_filter,
        approved_filter,
        min_props_filter,
    ])

    if needs_scan:
        all_docs = list(
            qs.order_by(order_by).only("part_number", "revision", "description", "category", "attrs", "processes")
        )
        coverage = _coverage_map(all_docs)
        filtered_docs = []
        meta = current_app.config.get("PROCESS_META", {})
        for p in all_docs:
            attrs = harvest_part_attrs(p)
            rev = _normalized_revision(p, attrs)
            groups = coverage.get((p.part_number, rev)) or set()
            proc_list = normalize_process_list(attrs, list(p.processes or []), meta)
            if has_pdf_filter is not None and ("pdf" in groups) != has_pdf_filter:
                continue
            if approved_filter and not _is_approved(attrs):
                continue
            if min_props_filter and not _min_props_ok(p, attrs, proc_list):
                continue
            if full_files_filter and not _full_files_ok(proc_list, groups, meta):
                continue
            filtered_docs.append(p)
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

    out = []
    for p in docs:
        attrs = harvest_part_attrs(p)
        pn = p.part_number
        rev = _normalized_revision(p, attrs)
        display_code = f"{pn}-{rev}" if rev else pn
        groups = coverage.get((pn, rev)) or set()
        out.append(
            {
                "id": f"{pn}::{rev}",
                "part_number": pn,
                "revision": rev,
                "display_code": display_code,
                "description": p.description or attrs.get("description") or "",
                "category": attrs.get("category") or p.category or "",
                "material": attrs.get("material", ""),
                "finish": attrs.get("finish", ""),
                "mass": attrs.get("mass", ""),
                "processes": normalize_process_list(attrs, list(p.processes or []), current_app.config.get("PROCESS_META", {})),
                "thumb_urls": thumb_urls_for(pn, rev),
                "has_pdf": "pdf" in groups,
                "has_png": "png" in groups,
                "has_dxf": "dxf" in groups,
                "has_step": "step" in groups,
                "has_datasheet": "datasheet" in groups,
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
    norm_rev = _normalized_revision(p, attrs)
    meta = current_app.config.get("PROCESS_META", {})
    proc_list = normalize_process_list(attrs, list(p.processes or []), meta)

    preview_urls = preview_png_urls_for(p.part_number, norm_rev)
    drawing_urls = drawing_png_urls_for(p.part_number, norm_rev)

    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")
    allow_public = public_file_urls_enabled()

    def to_url(f: PartFile):
        if allow_public and http_base and f.rel_path:
            return f"{http_base}/{f.rel_path}"
        return file_url_for(f)

    def file_label(f: PartFile) -> str:
        name = os.path.basename(f.rel_path or f.path or "")
        return name or "file"

    files = {"pdf": [], "dxf": [], "step": [], "edr": [], "3mf": [], "ply": [], "stl": []}
    for f in (
        PartFile.objects(part_number__iexact=p.part_number, revision__iexact=norm_rev)
        .only("ext_group", "rel_path", "path")
        .order_by("ext_group", "rel_path")
    ):
        if f.ext_group in files:
            files[f.ext_group].append({"url": to_url(f), "rel": f.rel_path or "", "name": file_label(f)})

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
                "description": p.description or attrs.get("description", ""),
                "revision": norm_rev,
                "display_code": f"{p.part_number}-{norm_rev}" if norm_rev else p.part_number,
                "category": attrs.get("category", ""),
                "material": attrs.get("material", ""),
                "finish": attrs.get("finish", ""),
                "mass": attrs.get("mass", ""),
                "processes": proc_list,
                "attributes": attrs,
            },
            "images": preview_urls,
            "drawing_urls": drawing_urls,
            "files": files,
            "whereused": wu_rows,
            "other_versions": other_versions,
            "jobs_orders": jobs_orders,
            "can_jobs_manage": can_jobs_manage,
            "can_orders_manage": can_orders_manage,
            "can_parts_delete": can_parts_delete,
            "can_parts_edit": can_parts_edit,
            "can_parts_note": can_parts_note,
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
    attrs = dict(p.attrs or {})
    attrs["notes"] = notes
    p.attrs = attrs
    p.updated_at = datetime.utcnow()
    p.save()
    try:
        log_action(
            "part.notes.update",
            resource_type="part",
            resource=f"{p.part_number}:{p.revision or ''}",
            meta={"notes_len": len(notes)},
        )
    except Exception:
        pass
    return jsonify({"ok": True, "notes": notes})


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

    attrs = dict(p.attrs or {})
    comments = attrs.get("comments")
    if not isinstance(comments, list):
        comments = []
    comment = {
        "ts": datetime.utcnow().isoformat(),
        "author": getattr(current_user, "email", "") or "",
        "text": text,
    }
    comments.append(comment)
    attrs["comments"] = comments
    p.attrs = attrs
    p.updated_at = datetime.utcnow()
    p.save()
    try:
        log_action(
            "part.comments.add",
            resource_type="part",
            resource=f"{p.part_number}:{p.revision or ''}",
            meta={"comment_len": len(text)},
        )
    except Exception:
        pass
    return jsonify({"ok": True, "comment": comment})


@bp.post("/parts/<pn>/refresh_files")
@login_required
@permissions_required("items.edit")
@csrf.exempt
def part_refresh_files(pn):
    pn = (pn or "").strip()
    data = request.get_json(silent=True) or {}
    rev_in = data.get("rev") if "rev" in data else request.args.get("rev")
    rev_clean = _clean_rev_input(rev_in)
    p = _find_part_doc(pn, rev_clean)
    if not p:
        return jsonify({"ok": False, "error": "not found"}), 404
    target_rev = _clean_rev_value(p.revision or "")
    found = discover_part_files(p.part_number, target_rev)
    recs = []
    for (group, is_dwg), meta in found.items():
        rec = dict(meta)
        rec["ext_group"] = group
        rec["is_dwg"] = bool(is_dwg)
        recs.append(rec)
    upserts = upsert_part_files(recs, p.part_number, target_rev)
    thumbs = generate_thumbs_for_parts([(p.part_number, target_rev)])
    try:
        log_action(
            "part.files.refresh",
            resource_type="part",
            resource=f"{p.part_number}:{target_rev}",
            meta={"found": len(recs), "upserts": upserts, "thumbs": thumbs},
        )
    except Exception:
        pass
    return jsonify(
        {
            "ok": True,
            "part_number": p.part_number,
            "revision": target_rev,
            "files_found": len(recs),
            "artifacts_upserted": upserts,
            "thumbnails_generated": thumbs,
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

    result = delete_part_and_refs(pn, rev)
    try:
        log_action("part.delete", resource_type="part", resource=f"{pn}:{rev}")
    except Exception:
        pass
    return jsonify({"ok": True, **result})
