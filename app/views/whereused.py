# app/views/whereused.py
from flask import Blueprint, request, jsonify
from mongoengine.queryset.visitor import Q
from app.models.bom import BOMLink
from app.models.part import Part
from app.extensions import csrf
from app.services.thumbs import thumb_urls_for

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
    sort_order = int(body.get("sortOrder", 1))     # 1 asc, -1 desc
    filters = body.get("filters", {})

    ALLOWED = {"parent_pn", "parent_desc", "qty", "uom", "alt_group"}
    if sort_field not in ALLOWED:
        sort_field = "parent_pn"

    q = Q(child_pn=pn)

    # parent_pn filter
    f = filters.get("parent_pn") or {}
    val = (f.get("value") or "").strip()
    if val:
        q &= Q(**{f"parent_pn__{_match_op(f.get('matchMode'))}": val})

    # parent_desc filter (JOIN via Part)
    fd = filters.get("parent_desc") or {}
    desc = (fd.get("value") or "").strip()
    if desc:
        op = _match_op(fd.get("matchMode"))
        parents = Part.objects(**{f"description__{op}": desc}).only("part_number")
        parent_set = [p.part_number for p in parents]
        if not parent_set:
            return jsonify({"data": [], "totalRecords": 0, "totalAll": BOMLink.objects(child_pn=pn).count()})
        q &= Q(parent_pn__in=parent_set)

    # alt_group filter
    fa = filters.get("alt_group") or {}
    alt = (fa.get("value") or "").strip()
    if alt:
        q &= Q(**{f"alt_group__{_match_op(fa.get('matchMode'))}": alt})

    # Query slice
    qs = BOMLink.objects(q).only("parent_pn", "qty", "uom", "alt_group")
    total_for_child = BOMLink.objects(child_pn=pn).count()
    filtered_count = qs.count()
    page = list(qs.skip(first).limit(rows))

    # Attach parent descriptions
    parent_pns = list({l.parent_pn for l in page})
    desc_map = {
        p.part_number: (p.description or "")
        for p in Part.objects(part_number__in=parent_pns).only("part_number", "description")
    }

    data = [{
        "parent_pn": l.parent_pn,
        "parent_desc": desc_map.get(l.parent_pn, ""),
        "qty": l.qty or 1.0,
        "uom": l.uom or "EA",
        "alt_group": l.alt_group or "",
        "parent_thumb_urls": thumb_urls_for(parent.part_number, parent.revision or None),
    } for l in page]

    # Sort the page (simple slice sort)
    reverse = (sort_order == -1)
    if sort_field == "qty":
        data.sort(key=lambda r: float(r.get("qty") or 0), reverse=reverse)
    else:
        data.sort(key=lambda r: (r.get(sort_field) or "").lower(), reverse=reverse)

    return jsonify({"data": data, "totalRecords": filtered_count, "totalAll": total_for_child})
