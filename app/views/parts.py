# app/views/parts.py
from flask import Blueprint, render_template, request, jsonify
from mongoengine.queryset.visitor import Q
from app.models.part import Part

bp = Blueprint("parts", __name__, url_prefix="/parts")

@bp.route("/browse")
def browse():
    return render_template("parts/browse.html")

@bp.route("/api/parts")
def api_parts():
    # DataTables server-side protocol
    draw   = int(request.args.get("draw", 1))
    start  = int(request.args.get("start", 0))
    length = int(request.args.get("length", 25))
    search_value = (request.args.get("search[value]") or "").strip()

    # 3 columns only (order matters!)
    columns = ["part_number", "description", "category"]

    # ordering
    order_col = int(request.args.get("order[0][column]", 0))
    order_dir = request.args.get("order[0][dir]", "asc")
    order_field = columns[order_col] if 0 <= order_col < len(columns) else "part_number"
    order_by = f"-{order_field}" if order_dir == "desc" else order_field

    # base query + global search
    q = Q()
    if search_value:
        q &= (Q(part_number__icontains=search_value) |
              Q(description__icontains=search_value) |
              Q(category__icontains=search_value))

    # per-column filters (supports '=value' for exact, else contains)
    for idx, field in enumerate(columns):
        val = (request.args.get(f"columns[{idx}][search][value]") or "").strip()
        if not val:
            continue
        if val.startswith("="):
            q &= Q(**{f"{field}__iexact": val[1:].strip()})
        else:
            q &= Q(**{f"{field}__icontains": val})

    total = Part.objects.count()
    qs = Part.objects(q)
    filtered = qs.count()

    docs = qs.order_by(order_by).only(*columns).skip(start).limit(length)

    # render PN as a link to the BOM browser (if you’ve added /bom/<pn>)
    data = []
    for p in docs:
        data.append([
            f'<a href="/bom/{p.part_number}">{p.part_number}</a>',
            p.description or "",
            p.category or "",
        ])

    return jsonify({
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": filtered,
        "data": data
    })

# Optional: distinct categories for a select filter (if you prefer a dropdown)
@bp.route("/api/parts/distinct/category")
def distinct_category():
    vals = Part._get_collection().distinct("category")
    # sort case-insensitive and skip blanks
    vals = sorted([v for v in vals if isinstance(v, str) and v], key=lambda s: s.lower())
    return jsonify(vals)
