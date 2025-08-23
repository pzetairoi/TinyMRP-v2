from flask import Blueprint, request, jsonify
from app.models.part import Part
from app.models.bom import BOMLink
from app.services.thumbs import thumb_urls_for

bp = Blueprint("bom_tree_api", __name__, url_prefix="/api")

def _pn_from_link_child(l):
    # prefer explicit child_pn, else take ReferenceField.child.part_number
    if hasattr(l, "child_pn") and l.child_pn:
        return l.child_pn
    c = getattr(l, "child", None)
    return getattr(c, "part_number", None) if c else None

def _pn_from_link_parent(l):
    if hasattr(l, "parent_pn") and l.parent_pn:
        return l.parent_pn
    p = getattr(l, "parent", None)
    return getattr(p, "part_number", None) if p else None

@bp.get("/bom_tree")
def bom_tree():
    pn = (request.args.get("pn") or "").strip()
    parent = (request.args.get("parent") or "").strip()

    # Helper to build a node dict from PN and optional link info
    def node_for_pn(child_pn: str, link=None):
        c = Part.objects(part_number=child_pn).only("part_number", "description", "revision").first()
        return {
            "key": child_pn,
            "leaf": False,  # unknown until expanded; TreeTable can lazy load
            "data": {
                "pn": child_pn,
                "desc": (c.description if c else ""),
                "rev": (c.revision or "") if c else "",
                "qty": getattr(link, "qty", None),
                "uom": getattr(link, "uom", None),
                "alt_group": (getattr(link, "alt_group", "") or "") if link else "",
                "thumb_urls": thumb_urls_for(child_pn, (c.revision if c else None)),
            },
        }

    # ROOT: node for pn + its immediate children
    if pn:
        p = Part.objects(part_number=pn).only("part_number", "description", "revision").first()
        if not p:
            return jsonify([])

        # Prefer string-field query if present; else ReferenceField
        if "parent_pn" in BOMLink._fields:
            links = BOMLink.objects(parent_pn=pn).only("child_pn", "qty", "uom", "alt_group")
        else:
            links = BOMLink.objects(parent=p).only("child", "qty", "uom", "alt_group")

        children = []
        for l in links:
            child_pn = _pn_from_link_child(l)
            if not child_pn:
                continue
            if child_pn == pn:  # avoid self-link
                continue
            children.append(node_for_pn(child_pn, l))

        root = {
            "key": p.part_number,
            "leaf": False,
            "data": {
                "pn": p.part_number,
                "desc": p.description or "",
                "rev": p.revision or "",
                "thumb_urls": thumb_urls_for(p.part_number, (p.revision or None)),
            },
            "children": children,
        }
        return jsonify([root])

    # LAZY CHILDREN: expanding an existing node by parent PN
    if parent:
        # Work with parent PN directly (don’t pass Part objects to filters wrongly)
        if "parent_pn" in BOMLink._fields:
            links = BOMLink.objects(parent_pn=parent).only("child_pn", "qty", "uom", "alt_group")
        else:
            parent_part = Part.objects(part_number=parent).only("id").first()
            links = BOMLink.objects(parent=parent_part).only("child", "qty", "uom", "alt_group")

        rows = []
        for l in links:
            child_pn = _pn_from_link_child(l)
            if not child_pn:
                continue
            if child_pn == parent:  # avoid self-link
                continue
            rows.append(node_for_pn(child_pn, l))
        return jsonify(rows)

    return jsonify([])
