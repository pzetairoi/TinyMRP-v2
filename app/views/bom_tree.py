# app/views/bom_tree.py
from flask import Blueprint, request, jsonify
from app.models.part import Part
from app.models.bom import BOMLink
from app.services.thumbs import preview_png_urls_for
from app.services.attrs import harvest_part_attrs

bp = Blueprint("bom_tree_api", __name__, url_prefix="/api")

def _has_children(pn: str) -> bool:
    if "parent_pn" in BOMLink._fields:
        return BOMLink.objects(parent_pn=pn).limit(1).count() > 0
    p = Part.objects(part_number=pn).only("id").first()
    if not p:
        return False
    return BOMLink.objects(parent=p).limit(1).count() > 0

def _node(pn: str, link=None):
    p = Part.objects(part_number=pn).first()
    attrs = harvest_part_attrs(p) if p else {}
    return {
        "key": pn,
        "leaf": not _has_children(pn),
        "data": {
            "pn": pn,
            "desc": attrs.get("description",""),
            "rev":  attrs.get("revision",""),
            "qty":  getattr(link,"qty",None),
            "uom":  getattr(link,"uom",None),
            "alt_group": getattr(link,"alt_group","") or "",
            "material":  attrs.get("material",""),
            "finish":    attrs.get("finish",""),
            "process":   ", ".join([x for x in attrs.get("processes",[]) if x]) or (attrs.get("process","") or ""),
            "thumb_urls": preview_png_urls_for(pn, attrs.get("revision")),
            "attrs": attrs,
        }
    }

@bp.get("/bom_tree")
def bom_tree():
    pn = (request.args.get("pn") or "").strip()
    print("request",request.args)
    parent = (request.args.get("parent") or "").strip()

    if pn:
        p = Part.objects(part_number=pn).first()
        if not p:
            return jsonify([])
        root = _node(pn)
        root["children"] = []   # lazy
        return jsonify([root])
 
    if parent:
        # children
        if "parent_pn" in BOMLink._fields:
            links = BOMLink.objects(parent_pn=parent).only("child_pn","qty","uom","alt_group")
            kids = []
            for l in links:
                child_pn = getattr(l, "child_pn", None)
                if child_pn and child_pn != parent:
                    kids.append(_node(child_pn, l))
            return jsonify(kids)
        else:
            pp = Part.objects(part_number=parent).only("id").first()
            if not pp:
                return jsonify([])
            links = BOMLink.objects(parent=pp).only("child","qty","uom","alt_group")
            kids = []
            for l in links:
                c = getattr(l, "child", None)
                child_pn = getattr(c, "part_number", None) if c else None
                if child_pn and child_pn != parent:
                    kids.append(_node(child_pn, l))
            return jsonify(kids)

    return jsonify([])
