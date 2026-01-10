# app/views/parts.py
from flask import Blueprint, request, jsonify, current_app, url_for
from flask_login import login_required, current_user
from mongoengine.queryset.visitor import Q
import re
from base64 import urlsafe_b64encode

from app.models.part import Part
from app.models.job import Job
from app.models.order import Order
from app.models.bom import BOMLink
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.extensions import csrf
from app.services.thumbs import thumb_urls_for, drawing_urls_for
from app.services.attrs import harvest_part_attrs
from app.models.artifact import PartFile
from app.views.whereused import _rows_for_child_pn
from app.services.processmeta import normalize_processes
from app.services.thumbs import preview_png_urls_for, drawing_png_urls_for
from app.services.acl import require_items_view, allowed_parts_for, part_is_allowed, user_has_permission
from app.services.audit import log_action

bp = Blueprint("parts_api", __name__, url_prefix="/api")


def _normalized_revision(p: Part, attrs: dict) -> str:
    rev = (attrs.get("revision") or p.revision or "").strip()
    return rev


def _resolve_rev_for_pn(pn: str, rev: str | None) -> str:
    rev = (rev or "").strip()
    if rev:
        return rev
    p = Part.objects(part_number__iexact=pn).order_by("-updated_at").first()
    if not p:
        return ""
    attrs = harvest_part_attrs(p)
    return (attrs.get("revision") or p.revision or "").strip()


def _parent_candidates(child_pn: str, child_rev: str | None, max_rows: int = 50):
    q = BOMLink.objects(child_pn=child_pn)
    if child_rev is not None and "child_rev" in BOMLink._fields:
        q = q.filter(child_rev=(child_rev or ""))
        if (child_rev or "").strip() and q.limit(1).count() == 0:
            q = BOMLink.objects(child_pn=child_pn, child_rev="")
    parents = []
    for l in q.limit(max_rows):
        parent_pn = (getattr(l, "parent_pn", None) or "").strip()
        if not parent_pn:
            continue
        parent_rev = (getattr(l, "parent_rev", "") or "").strip()
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
        rev_clean = (rev or "").strip()
        if rev_clean:
            used.add((pn_clean.lower(), rev_clean.lower()))
        else:
            resolved = _resolve_rev_for_pn(pn_clean, "")
            if resolved:
                used.add((pn_clean.lower(), resolved.lower()))
            used.add((pn_clean.lower(), ""))
    return used


def _match_used(used: set[tuple[str, str]], pn: str, rev: str | None) -> bool:
    pn_l = (pn or "").strip().lower()
    rev_l = (rev or "").strip().lower()
    return (pn_l, rev_l) in used or (pn_l, "") in used


def _part_label(pn: str, rev: str | None) -> dict:
    resolved_rev = _resolve_rev_for_pn(pn, rev)
    p = Part.objects(part_number__iexact=pn, revision__iexact=resolved_rev).first() \
        or Part.objects(part_number__iexact=pn).order_by("-updated_at").first()
    attrs = harvest_part_attrs(p) if p else {}
    desc = attrs.get("description") or (p.description if p else "") or ""
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
        if not val:
            return q
        for t in _terms(val):
            or_q = Q()
            for fld in fields:
                or_q = or_q | Q(**{f"{fld}__icontains": t})
            q = q & or_q
        return q

    q = Q()
    q = add_filter(q, "part_number", "part_number")
    q = add_filter(q, "revision", "revision")
    q = add_filter(q, "description", "description")
    q = add_filter(q, "category", "category")
    q = add_filter(q, "material", "attrs__material")
    q = add_filter(q, "finish", "attrs__finish")
    proc_key = "process" if "process" in filters else "processes"
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

    # Optional job filter: limit to BOM parts for that job unless explicitly bypassed
    job_id = body.get("job") or request.args.get("job")
    job_filter_enabled = bool(job_id) and str(body.get("job_only", "true")).lower() != "false"
    if job_filter_enabled and job_id:
        job = Job.objects(id=job_id).first()
        if job and job.bom:
            pn_list = list({(l.pn or "").strip() for l in job.bom if (l.pn or "").strip()})
            if pn_list:
                job_q = Q()
                for pn in pn_list:
                    job_q = job_q | Q(part_number__iexact=pn)
                q = q & job_q

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
    filtered = qs.count()
    docs = (
        qs.order_by(order_by)
        .only("part_number", "revision", "description", "category", "attrs", "processes")
        .skip(first)
        .limit(rows)
    )

    out = []
    for p in docs:
        attrs = harvest_part_attrs(p)
        pn = p.part_number
        rev = _normalized_revision(p, attrs)
        display_code = f"{pn}-{rev}" if rev else pn
        out.append(
            {
                "id": f"{pn}::{rev}",
                "part_number": pn,
                "revision": rev,
                "display_code": display_code,
                "description": attrs.get("description") or p.description or "",
                "category": attrs.get("category") or p.category or "",
                "material": attrs.get("material", ""),
                "finish": attrs.get("finish", ""),
                "mass": attrs.get("mass", ""),
                "processes": normalize_processes(attrs, current_app.config.get("PROCESS_META", {})),
                "thumb_urls": thumb_urls_for(pn, rev or None),
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
        rev = request.args.get("rev") or ""
        p = Part.objects(part_number__iexact=pn, revision__iexact=rev).first()
        if not p:
            p = Part.objects(part_number__iexact=pn).order_by("-updated_at").first()
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
    proc_list = normalize_processes(attrs, meta)

    preview_urls = preview_png_urls_for(p.part_number, norm_rev)
    drawing_urls = drawing_png_urls_for(p.part_number, norm_rev)

    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")

    def to_url(f: PartFile):
        if http_base and f.rel_path:
            return f"{http_base}/{f.rel_path}"
        return f"/files/view/{urlsafe_b64encode((f.path or '').encode()).decode()}"

    files = {"pdf": [], "dxf": [], "step": [], "edr": [], "3mf": []}
    for f in (
        PartFile.objects(part_number__iexact=p.part_number, revision__iexact=norm_rev)
        .only("ext_group", "rel_path", "path")
        .order_by("ext_group", "rel_path")
    ):
        if f.ext_group in files:
            files[f.ext_group].append({"url": to_url(f), "rel": f.rel_path})

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
                "description": attrs_v.get("description") or op.description or "",
                "thumb_urls": thumb_urls_for(pn_key, rev_v or None),
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

    return jsonify(
        {
            "part": {
                "part_number": p.part_number,
                "description": attrs.get("description", ""),
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
        }
    )
