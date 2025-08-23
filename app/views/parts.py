# app/views/parts.py
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
from mongoengine.queryset.visitor import Q
import re
from base64 import urlsafe_b64encode

# Import necessary models and services
from app.models.part import Part
from app.extensions import csrf
from app.services.thumbs import thumb_urls_for, drawing_urls_for
from app.services.attrs import harvest_part_attrs
from app.models.artifact import PartFile



bp = Blueprint("parts_api", __name__, url_prefix="/api")

@login_required
@bp.route("/parts_lazy", methods=["GET", "POST"])
@csrf.exempt 
def parts_lazy():
    body = request.get_json(force=True, silent=True) or {}
    first = int(body.get("first", 0))
    rows = int(body.get("rows", 25))
    sort_field = (body.get("sortField") or "part_number")
    sort_order = int(body.get("sortOrder", 1))  # 1 asc, -1 desc
    order_by = f"-{sort_field}" if sort_order == -1 else sort_field
    filters = body.get("filters", {})

    ALLOWED = {"part_number", "description", "category"}
    if sort_field not in ALLOWED:
        sort_field = "part_number"
    order_by = f"-{sort_field}" if sort_order == -1 else sort_field

    def add_filter(q: Q, field: str):
        f = filters.get(field) or {}
        val = (f.get("value") or "").strip()
        mode = (f.get("matchMode") or "contains")
        if not val:
            return q
        suffix = {
            "contains": "icontains",
            "equals": "iexact",
            "startsWith": "istartswith",
            "endsWith": "iendswith",
        }.get(mode, "icontains")
        return q & Q(**{f"{field}__{suffix}": val})

    q = Q()
    for fld in ("part_number","revision", "description","revision", "category"):
        q = add_filter(q, fld)

    qs = Part.objects(q)
    filtered = qs.count()

    docs = qs.order_by(order_by).only("part_number","revision", "description", "category").skip(first).limit(rows)
    data = [{"part_number": p.part_number,
             "revision": p.revision or "", 
             "description": p.description or "",
             "category": p.category or ""} for p in docs]
    
    out = []
    for p in data:  # p is your Part doc
        pn = p["part_number"]
        rev = (p["revision"] or None)  # pass None so helper prefers "" then latest
        out.append({
            "part_number": pn,
            "description": p["description"],
            "category": p["category"],
            "revision": rev,
            # 👇 always include thumbnail candidates
            "thumb_urls": thumb_urls_for(pn, rev),
        })

    return jsonify({"data": out, "totalRecords": filtered})




@bp.get("/part_detail")
def part_detail():
    pn = (request.args.get("pn") or "").strip()
    p = Part.objects(part_number=pn).first()
    if not p:
        return jsonify({"error": "not found"}), 404

    attrs = harvest_part_attrs(p)
    material = attrs.get("material","")
    finish   = attrs.get("finish","")
    mass     = attrs.get("mass","")
    processes= ", ".join(attrs.get("processes", [])) or attrs.get("process","")

    images   = thumb_urls_for(p.part_number, (p.revision or None))
    drawings = drawing_urls_for(p.part_number, (p.revision or None))

    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")
    def to_url(f: PartFile):
        if http_base and f.rel_path:
            return f"{http_base}/{f.rel_path}"
        return f"/files/view/{urlsafe_b64encode((f.path or '').encode()).decode()}"

    files = {"pdf": [], "dxf": [], "step": [], "edr": [], "3mf": []}
    for f in PartFile.objects(part_number=p.part_number).only("ext_group","rel_path","path").order_by("ext_group","rel_path"):
        if f.ext_group in files:
            files[f.ext_group].append({"url": to_url(f), "rel": f.rel_path})

    return jsonify({
    "part": {
        "part_number": p.part_number,
        "description": attrs.get("description", ""),
        "revision": attrs.get("revision", ""),
        "category": attrs.get("category", ""),
        "material": attrs.get("material", ""),
        "finish": attrs.get("finish", ""),
        "mass": attrs.get("mass", ""),
        "processes": ", ".join(attrs.get("processes", [])),  # UI string; full list is in attributes
        "attributes": attrs,  # ← full, normalized, complete
    },
    "images": images,
    "drawing_urls": drawings,
    "files": files,
    })