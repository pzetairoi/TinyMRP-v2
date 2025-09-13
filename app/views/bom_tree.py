# app/views/bom_tree.py
from flask import Blueprint, request, jsonify
from flask_login import login_required
from app.models.part import Part
from app.models.bom import BOMLink
from app.services.thumbs import preview_png_urls_for
from app.services.attrs import harvest_part_attrs
from app.services.acl import require_items_view
from app.services.audit import log_action

bp = Blueprint("bom_tree_api", __name__, url_prefix="/api")

def _has_children(pn: str, rev: str | None = None) -> bool:
    if "parent_pn" in BOMLink._fields:
        if rev is not None and "parent_rev" in BOMLink._fields:
            return BOMLink.objects(parent_pn=pn, parent_rev=(rev or "")).limit(1).count() > 0
        return BOMLink.objects(parent_pn=pn).limit(1).count() > 0
    p = Part.objects(part_number=pn).only("id").first()
    if not p:
        return False
    return BOMLink.objects(parent=p).limit(1).count() > 0

def _node(pn: str, link=None, rev: str | None = None):
    # Prefer specific revision when provided, else pick latest by updated_at
    if rev is not None:
        p = Part.objects(part_number=pn, revision=rev).first() or \
            Part.objects(part_number=pn).order_by("-updated_at").first()
    else:
        p = Part.objects(part_number=pn).order_by("-updated_at").first()
    attrs = harvest_part_attrs(p) if p else {}
    return {
        "key": pn,
        "leaf": not _has_children(pn, attrs.get("revision")),
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
@login_required
@require_items_view
def bom_tree():
    pn = (request.args.get("pn") or "").strip()
    rev = request.args.get("rev")  # keep None vs ""
    parent = (request.args.get("parent") or "").strip()
    parent_rev = request.args.get("parent_rev")
    parent_rev = request.args.get("parent_rev")

    if pn:
        # Build root node for specific revision if provided; else latest
        if rev is not None:
            p = Part.objects(part_number=pn, revision=(rev or "")).first() or \
                Part.objects(part_number=pn).order_by("-updated_at").first()
        else:
            p = Part.objects(part_number=pn).order_by("-updated_at").first()
        if not p:
            return jsonify([])
        root = _node(p.part_number, rev=(p.revision or None))
        root["children"] = []   # lazy
        try:
            log_action("bom.view", resource_type="bom", resource=f"root:{p.part_number}:{p.revision or ''}")
        except Exception:
            pass
        return jsonify([root])
 
    if parent:
        # children
        if "parent_pn" in BOMLink._fields:
            if parent_rev is not None and "parent_rev" in BOMLink._fields:
                links = BOMLink.objects(parent_pn=parent, parent_rev=(parent_rev or "")).only("child_pn","qty","uom","alt_group","child_rev")
            else:
                links = BOMLink.objects(parent_pn=parent).only("child_pn","qty","uom","alt_group","child_rev")
            kids = []
            for l in links:
                child_pn = getattr(l, "child_pn", None)
                if child_pn and child_pn != parent:
                    c_rev = getattr(l, "child_rev", None) if hasattr(l, "child_rev") else None
                    kids.append(_node(child_pn, l, rev=c_rev))
            try:
                log_action("bom.view", resource_type="bom", resource=f"children:{parent}:{(parent_rev or '')}")
            except Exception:
                pass
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
            try:
                log_action("bom.view", resource_type="bom", resource=f"children:{parent}")
            except Exception:
                pass
            return jsonify(kids)

    return jsonify([])
