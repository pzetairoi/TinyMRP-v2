# app/views/parts.py
from flask import Blueprint, request, jsonify
from mongoengine.queryset.visitor import Q
from app.models.part import Part

bp = Blueprint("parts_api", __name__, url_prefix="/api")

@bp.post("/parts_lazy")
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
    for fld in ("part_number", "description", "category"):
        q = add_filter(q, fld)

    qs = Part.objects(q)
    filtered = qs.count()

    docs = qs.order_by(order_by).only("part_number", "description", "category").skip(first).limit(rows)
    data = [{"part_number": p.part_number, "description": p.description or "", "category": p.category or ""} for p in docs]

    return jsonify({"data": data, "totalRecords": filtered})
