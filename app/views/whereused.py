# app/views/whereused.py
from flask import Blueprint, request, jsonify
from mongoengine.queryset.visitor import Q
from app.models.bom import BOMLink
from app.models.part import Part
from app.extensions import csrf

bp = Blueprint("whereused_api", __name__, url_prefix="/api")

def _match_op(mode: str) -> str:
    return {
        "contains": "icontains",
        "equals": "iexact",
        "startsWith": "istartswith",
        "endsWith": "iendswith",
    }.get((mode or "").strip(), "icontains")

@bp.post("/whereused_lazy")
@csrf.exempt
def whereused_lazy():
    body = request.get_json(force=True, silent=True) or {}
    pn = (body.get("pn") or "").strip()
    first = int(body.get("first", 0))
    rows = int(body.get("rows", 25))
    sort_field = (body.get("sortField") or "parent_pn")
    sort_order = int(body.get("sortOrder", 1))  # 1 asc, -1 desc
    filters = body.get("filters", {})

    ALLOWED = {"parent_pn", "parent_desc", "qty", "uom", "alt_group"}
    if sort_field not in ALLOWED:
        sort_field = "parent_pn"

    q = Q(child_pn=pn)

    # parent_pn filter
    if "parent_pn" in filters:
        f = filters["parent_pn"] or {}
        val = (f.get("value") or "").strip()
        if val:
            q &= Q(**{f"parent_pn__{_match_op(f.get('matchMode'))}": val})

    # alt_group filter
    if "alt_group" in filters:
        f = filters["alt_group"] or {}
        val = (f.get("value") or "").strip()
        if val:
            q &= Q(**{f"alt_group__{_match_op(f.get('matchMode'))}": val})

    # We'll build a slice and attach parent_desc (needs a lookup)
    qs = BOMLink.objects(q).only("parent_pn", "qty", "uom", "alt_group")

    total_for_child = BOMLink.objects(child_pn=pn).count()
    filtered_count = qs.count()

    # Fetch page
    page = list(qs.skip(first).limit(rows))

    # Attach parent descriptions
    parent_pns = list({l.parent_pn for l in page})
    desc_map = {p.part_number: (p.description or "")
                for p in Part.objects(part_number__in=parent_pns).only("part_number", "description")}

    # Build row objects
    data = []
    for l in page:
        data.append({
            "parent_pn": l.parent_pn,
            "parent_desc": desc_map.get(l.parent_pn, ""),
            "qty": l.qty or 1.0,
            "uom": l.uom or "EA",
            "alt_group": l.alt_group or ""
        })

    # Server-side sort for the slice (good enough for UI; full-accurate sort would require pre-join)
    reverse = (sort_order == -1)
    data.sort(key=lambda r: r.get(sort_field, ""), reverse=reverse)

    return jsonify({"data": data, "totalRecords": filtered_count, "totalAll": total_for_child})