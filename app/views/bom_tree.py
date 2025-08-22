# app/views/bom_tree.py
from flask import Blueprint, request, jsonify
from app.models.bom import BOMLink
from app.models.part import Part
from app.extensions import csrf

bp = Blueprint("bom_tree_api", __name__, url_prefix="/api")

def _node_for_part(p: Part) -> dict:
    return {
        "key": p.part_number,
        "leaf": False,  # we don't know yet; front-end will lazy fetch
        "data": {
            "pn": p.part_number,
            "desc": p.description,
            "rev": p.revision or "",
            "thumb_urls": thumb_urls_for(p.part_number, p.revision or None),
        },
        "children": [],  # optional; we attach on expand
    }

@bp.get("/bom_tree")
def bom_tree():
    pn = (request.args.get("pn") or "").strip()
    parent = (request.args.get("parent") or "").strip()
    # Root request
    if pn:
        p = Part.objects(part_number=pn).first()
        if not p:
            return jsonify([])
        # children for the root
        kids = []
        for l in BOMLink.objects(parent=pn):
            c = Part.objects(part_number=l.child).first()
            if not c:
                continue
            kids.append({
                "key": c.part_number,
                "leaf": False,
                "data": {
                    "pn": c.part_number,
                    "desc": c.description,
                    "rev": c.revision or "",
                    "qty": l.qty,
                    "uom": l.uom,
                    "alt_group": l.alt_group or "",
                    "thumb_urls": thumb_urls_for(c.part_number, c.revision or None),
                },
            })
        return jsonify([_node_for_part(p) | {"children": kids}])

    # Lazy children request for an expanded node
    if parent:
        rows = []
        for l in BOMLink.objects(parent=parent):
            c = Part.objects(part_number=l.child).first()
            if not c:
                continue
            rows.append({
                "key": c.part_number,
                "leaf": False,
                "data": {
                    "pn": c.part_number,
                    "desc": c.description,
                    "rev": c.revision or "",
                    "qty": l.qty,
                    "uom": l.uom,
                    "alt_group": l.alt_group or "",
                    "thumb_urls": thumb_urls_for(c.part_number, c.revision or None),
                },
            })
        return jsonify(rows)

    return jsonify([])