# app/views/parts.py
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from mongoengine.queryset.visitor import Q
import re
from base64 import urlsafe_b64encode

from app.models.part import Part
from app.models.job import Job
from app.extensions import csrf
from app.services.thumbs import thumb_urls_for, drawing_urls_for
from app.services.attrs import harvest_part_attrs
from app.models.artifact import PartFile
from app.views.whereused import _rows_for_child_pn
from app.services.processmeta import normalize_processes
from app.services.thumbs import preview_png_urls_for, drawing_png_urls_for
from app.services.acl import require_items_view, allowed_parts_for
from app.services.audit import log_action

bp = Blueprint("parts_api", __name__, url_prefix="/api")


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
                q = q & Q(part_number__in=pn_list)

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
        rev = p.revision or ""
        out.append(
            {
                "id": f"{pn}::{rev}",
                "part_number": pn,
                "revision": rev,
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
        p = Part.objects(part_number=pn, revision=rev).first()
        if not p:
            p = Part.objects(part_number=pn).order_by("-updated_at").first()
    else:
        p = Part.objects(part_number=pn).order_by("-updated_at").first()
    if not p:
        return jsonify({"error": "not found"}), 404

    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set):
            key = (p.part_number, p.revision or "")
            if key not in allowed:
                try:
                    log_action("part.view.deny", resource_type="part", resource=f"{key[0]}:{key[1]}")
                except Exception:
                    pass
                return jsonify({"error": "forbidden"}), 403
    except Exception:
        pass

    attrs = harvest_part_attrs(p)
    meta = current_app.config.get("PROCESS_META", {})
    proc_list = normalize_processes(attrs, meta)

    preview_urls = preview_png_urls_for(p.part_number, p.revision)
    drawing_urls = drawing_png_urls_for(p.part_number, p.revision)

    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")

    def to_url(f: PartFile):
        if http_base and f.rel_path:
            return f"{http_base}/{f.rel_path}"
        return f"/files/view/{urlsafe_b64encode((f.path or '').encode()).decode()}"

    files = {"pdf": [], "dxf": [], "step": [], "edr": [], "3mf": []}
    for f in (
        PartFile.objects(part_number__iexact=p.part_number, revision__iexact=p.revision)
        .only("ext_group", "rel_path", "path")
        .order_by("ext_group", "rel_path")
    ):
        if f.ext_group in files:
            files[f.ext_group].append({"url": to_url(f), "rel": f.rel_path})

    wu_rows = _rows_for_child_pn(p.part_number, p.revision)

    other_versions = []
    for op in (
        Part.objects(part_number=pn)
        .only("part_number", "revision", "description", "category", "attrs", "updated_at")
        .order_by("-updated_at")
    ):
        attrs_v = harvest_part_attrs(op)
        rev_v = attrs_v.get("revision", "") or op.revision or ""
        other_versions.append(
            {
                "id": f"{pn}::{rev_v}",
                "part_number": pn,
                "revision": rev_v,
                "description": attrs_v.get("description") or op.description or "",
                "thumb_urls": thumb_urls_for(pn, rev_v or None),
            }
        )

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
                "revision": attrs.get("revision", ""),
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
        }
    )
