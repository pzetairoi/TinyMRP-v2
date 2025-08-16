# app/views/bom_tree.py
from flask import Blueprint, request, jsonify
from app.models.bom import BOMLink
from app.models.part import Part

bp = Blueprint("bom_tree_api", __name__, url_prefix="/api")

@bp.get("/bom_tree")
def bom_tree():
    """GET /api/bom_tree?pn=ROOT (root) or /api/bom_tree?parent=PN (children)"""
    pn = (request.args.get("pn") or "").strip()
    parent = (request.args.get("parent") or "").strip()

    # root node
    if pn and not parent:
        part = Part.objects(part_number=pn).only("description").first()
        label = f"{pn}" + (f" — {part.description}" if part and part.description else "")
        has_children = BOMLink.objects(parent_pn=pn).first() is not None
        return jsonify([{"key": pn, "label": label, "leaf": not has_children}])

    # children
    p = parent or pn
    links = BOMLink.objects(parent_pn=p)
    out = []
    for l in links:
        child = Part.objects(part_number=l.child_pn).only("description").first()
        base = f"{l.child_pn}" + (f" — {child.description}" if child and child.description else "")
        label = f"{base} ×{l.qty:g}"
        has_children = BOMLink.objects(parent_pn=l.child_pn).first() is not None
        out.append({"key": l.child_pn, "label": label, "leaf": not has_children})
    return jsonify(out)
