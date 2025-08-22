# at top with your other imports
from app.services.thumbs import thumb_urls_for
from app.models.part import Part
from app.models.bom import BOMLink
from flask import Blueprint, request, jsonify

bp = Blueprint("bom_tree_api", __name__, url_prefix="/api")

def _pn_from_link_child(l):
    # Prefer explicit child_pn string; otherwise take ReferenceField.part_number
    if hasattr(l, "child_pn") and l.child_pn:
        return l.child_pn
    if hasattr(l, "child") and l.child:
        try:
            return l.child.part_number
        except Exception:
            return None
    return None

def _pn_from_link_parent(l):
    if hasattr(l, "parent_pn") and l.parent_pn:
        return l.parent_pn
    if hasattr(l, "parent") and l.parent:
        try:
            return l.parent.part_number
        except Exception:
            return None
    return None

@bp.get("/bom_tree")
def bom_tree():
    pn = (request.args.get("pn") or "").strip()
    parent = (request.args.get("parent") or "").strip()

    # ROOT: build node for pn and preload its immediate children
    if pn:
        p = Part.objects(part_number=pn).first()
        if not p:
            return jsonify([])

        children = []
        # support either parent_pn (string) or parent (ref)
        # try string first
        q = BOMLink.objects(parent_pn=pn) if "parent_pn" in BOMLink._fields else BOMLink.objects(parent=p)
        for l in q:
            child_pn = _pn_from_link_child(l)
            if not child_pn:
                continue
            # Avoid querying if we already have the child Part object
            c = l.child if getattr(l, "child", None) else Part.objects(part_number=child_pn).first()
            children.append({
                "key": child_pn,
                "leaf": False,
                "data": {
                    "pn": child_pn,
                    "desc": (c.description if c else ""),
                    "rev": (c.revision if c and c.revision is not None else ""),
                    "qty": getattr(l, "qty", None),
                    "uom": getattr(l, "uom", None),
                    "alt_group": getattr(l, "alt_group", "") or "",
                    "thumb_urls": thumb_urls_for(child_pn, (c.revision if c else None)),
                }
            })

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

    # LAZY CHILDREN: expanding an existing node
    if parent:
        rows = []
        # same dual-shape support as above
        q = BOMLink.objects(parent_pn=parent) if "parent_pn" in BOMLink._fields else BOMLink.objects(parent=Part.objects(part_number=parent).first())
        for l in q:
            child_pn = _pn_from_link_child(l)
            if not child_pn:
                continue
            c = l.child if getattr(l, "child", None) else Part.objects(part_number=child_pn).first()
            rows.append({
                "key": child_pn,
                "leaf": False,
                "data": {
                    "pn": child_pn,
                    "desc": (c.description if c else ""),
                    "rev": (c.revision if c and c.revision is not None else ""),
                    "qty": getattr(l, "qty", None),
                    "uom": getattr(l, "uom", None),
                    "alt_group": getattr(l, "alt_group", "") or "",
                    "thumb_urls": thumb_urls_for(child_pn, (c.revision if c else None)),
                }
            })
        return jsonify(rows)

    return jsonify([])
