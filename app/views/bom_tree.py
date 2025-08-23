from flask import Blueprint, request, jsonify
from app.models.part import Part
from app.models.bom import BOMLink
from app.services.thumbs import thumb_urls_for
from app.services.attrs import harvest_part_attrs


bp = Blueprint("bom_tree_api", __name__, url_prefix="/api")

def _pn_from_link_child(l):
    if hasattr(l, "child_pn") and l.child_pn:
        return l.child_pn
    c = getattr(l, "child", None)
    return getattr(c, "part_number", None) if c else None

@bp.get("/bom_tree")
def bom_tree():
    pn = (request.args.get("pn") or "").strip()
    parent = (request.args.get("parent") or "").strip()

    def node_for_pn(child_pn: str, link=None):
        c = Part.objects(part_number=child_pn).first()
        attrs = harvest_part_attrs(c) if c else {}
        material = attrs.get("material","")
        finish   = attrs.get("finish","")
        desc     = attrs.get("description","")
        rev      = attrs.get("revision","")

        return {
            "key": child_pn,
            "leaf": False,
            "data": {
                "pn": child_pn,
                "desc": desc,
                "rev": rev,
                "qty": getattr(link, "qty", None),
                "uom": getattr(link, "uom", None),
                "alt_group": getattr(link, "alt_group", "") or "",
                "material": material,
                "finish": finish,
                "thumb_urls": thumb_urls_for(child_pn, (rev or None)),
                "attrs": attrs,   # <- full attributes available to the UI (optional today)
            },
        }

    # ROOT
    if pn:
        p = Part.objects(part_number=pn).first()
        if not p: 
            return jsonify([])
        root_attrs = harvest_part_attrs(p)
        
        if "parent_pn" in BOMLink._fields:
            links = BOMLink.objects(parent_pn=pn).only("child_pn", "qty", "uom", "alt_group")
        else:
            links = BOMLink.objects(parent=p).only("child", "qty", "uom", "alt_group")

        children = []
        for l in links:
            child_pn = _pn_from_link_child(l)
            if not child_pn or child_pn == pn:   # avoid self-link
                continue
            children.append(node_for_pn(child_pn, l))

        root = {
        "key": p.part_number,
        "leaf": False,
        "data": {
            "pn": p.part_number,
            "desc": root_attrs.get("description",""),
            "rev": root_attrs.get("revision",""),
            "material": root_attrs.get("material",""),
            "finish": root_attrs.get("finish",""),
            "thumb_urls": thumb_urls_for(p.part_number, (root_attrs.get("revision") or None)),
            "attrs": root_attrs,
        },
        "children": children,
        }
        return jsonify([root])

    # LAZY
    if parent:
        if "parent_pn" in BOMLink._fields:
            links = BOMLink.objects(parent_pn=parent).only("child_pn", "qty", "uom", "alt_group")
        else:
            parent_part = Part.objects(part_number=parent).only("id").first()
            links = BOMLink.objects(parent=parent_part).only("child", "qty", "uom", "alt_group")

        rows = []
        for l in links:
            child_pn = _pn_from_link_child(l)
            if not child_pn or child_pn == parent:
                continue
            rows.append(node_for_pn(child_pn, l))
        return jsonify(rows)

    return jsonify([])
