# app/views/whereused.py
from flask import Blueprint, request, jsonify
from mongoengine.queryset.visitor import Q
from app.models.bom import BOMLink
from app.models.part import Part

bp = Blueprint("whereused_api", __name__, url_prefix="/api")

@bp.post("/whereused_lazy")
def whereused_lazy():
    body = request.get_json(force=True, silent=True) or {}
    pn = (body.get("pn") or "").strip()
    first = int(body.get("first", 0)); rows = int(body.get("rows", 25))
    sort_field = (body.get("sortField") or "parent_pn"); sort_order = int(body.get("sortOrder", 1))
    filters = body.get("filters", {})

    q = Q(child_pn=pn)
    # optional filters
    def fld(f): return (filters.get(f) or {}).get("value") or ""
    f_parent = fld("parent_pn").strip(); f_desc = fld("parent_desc").strip(); f_alt = fld("alt_group").strip()
    if f_parent: q &= Q(parent_pn__icontains=f_parent)
    if f_alt:    q &= Q(alt_group__icontains=f_alt)

    # pre-fetch slice (we’ll sort in Python for the slice)
    all_qs = list(BOMLink.objects(q).only("parent_pn","qty","uom","alt_group")[first:first+rows])
    def parent_desc(ppn):
        p = Part.objects(part_number=ppn).only("description").first()
        return p.description if p else ""

    rows_data = [[l.parent_pn, parent_desc(l.parent_pn), l.qty or 1.0, l.uom or "EA", l.alt_group or ""] for l in all_qs]

    reverse = (sort_order == -1)
    if sort_field == "parent_pn":   rows_data.sort(key=lambda r: r[0], reverse=reverse)
    elif sort_field == "parent_desc": rows_data.sort(key=lambda r: r[1], reverse=reverse)

    total = BOMLink.objects(child_pn=pn).count()
    filtered = BOMLink.objects(q).count()
    return jsonify({"data": rows_data, "totalRecords": filtered, "totalAll": total})
