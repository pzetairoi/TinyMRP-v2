from flask import Blueprint, render_template, request, jsonify
from mongoengine.queryset.visitor import Q
from ..models.bom import BOMLink
from ..models.part import Part

bp = Blueprint("bom", __name__, url_prefix="/bom")

@bp.route("/<pn>")
def browser(pn):
    # Main page with tabs (Tree + Where-used)
    # If part exists, we’ll show desc; else we still let you browse the links.
    part = Part.objects(part_number=pn).first()
    return render_template("tinylib/bom/browser.html", pn=pn, part=part)

# ---------- Tree (jsTree) ----------
@bp.route("/api/tree")
def api_tree():
    """
    jsTree lazy loader: expects ?pn=ROOTPN or ?id=NODEPN (when expanding)
    Returns list of nodes: { id, text, children: bool, icon?, data? }
    """
    pn = (request.args.get("pn") or "").strip()
    node_id = (request.args.get("id") or "").strip()  # jsTree passes id on expand

    # root request
    if pn and not node_id:
        p = Part.objects(part_number=pn).first()
        text = pn if not p else f"{p.part_number} — {p.description or ''}"
        has_children = BOMLink.objects(parent_pn=pn).first() is not None
        return jsonify([{
            "id": pn,
            "text": text,
            "children": bool(has_children),
            "icon": "bi bi-box",  # optional Bootstrap icon class
            "data": {"pn": pn}
        }])

    # children request (expand node)
    parent = node_id or pn
    links = BOMLink.objects(parent_pn=parent)
    out = []
    for link in links:
        child = Part.objects(part_number=link.child_pn).only("part_number", "description").first()
        label = link.child_pn if not child else f"{child.part_number} — {child.description or ''}"
        # does child have children?
        has_kids = BOMLink.objects(parent_pn=link.child_pn).first() is not None
        out.append({
            "id": link.child_pn,
            "text": f"{label}  ×{link.qty:g}",
            "children": bool(has_kids),
            "icon": "bi bi-caret-right",
            "data": {"pn": link.child_pn, "qty": link.qty, "uom": link.uom}
        })
    return jsonify(out)

# ---------- Where-used (DataTables server-side) ----------
@bp.route("/api/whereused")
def api_whereused():
    pn = (request.args.get("pn") or "").strip()
    draw   = int(request.args.get("draw", 1))
    start  = int(request.args.get("start", 0))
    length = int(request.args.get("length", 25))
    search_value = (request.args.get("search[value]") or "").strip()

    columns = ["parent_pn", "parent_desc", "qty", "uom", "alt_group"]
    q = Q(child_pn=pn)

    if search_value:
        # allow parent PN / description search
        parents = Part.objects(Q(part_number__icontains=search_value) | Q(description__icontains=search_value)).only("part_number")
        parent_set = set([p.part_number for p in parents])
        if parent_set:
            q &= Q(parent_pn__in=list(parent_set))
        else:
            q &= Q(parent_pn__icontains=search_value)

    order_col = int(request.args.get("order[0][column]", 0))
    order_dir = request.args.get("order[0][dir]", "asc")
    order_field = columns[order_col] if 0 <= order_col < len(columns) else "parent_pn"
    # mongoengine order_by needs field names we actually fetch below, so keep simple:
    # We'll sort in Python just for this small dataset; optimize later with projection.
    links = list(BOMLink.objects(q)[start:start+length])
    total = BOMLink.objects(child_pn=pn).count()
    filtered = BOMLink.objects(q).count()

    # Build rows
    rows = []
    for l in links:
        parent = Part.objects(part_number=l.parent_pn).only("description").first()
        rows.append([
            l.parent_pn,
            (parent.description if parent else ""),
            l.qty or 1.0,
            l.uom or "EA",
            l.alt_group or ""
        ])

    # naive sort on client slice (optional)
    reverse = (order_dir == "desc")
    if order_field == "parent_pn":
        rows.sort(key=lambda r: r[0], reverse=reverse)
    elif order_field == "parent_desc":
        rows.sort(key=lambda r: r[1], reverse=reverse)

    return jsonify({
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": filtered,
        "data": rows
    })
