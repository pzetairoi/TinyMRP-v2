# app/views/bom_tree.py
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
from app.models.artifact import PartFile
from app.models.part import Part
from app.models.bom import BOMLink
from app.services.thumbs import preview_png_urls_for
from app.services.attrs import harvest_part_attrs
from app.services.processmeta import normalize_processes
from flask_login import current_user
from app.services.acl import allowed_parts_for, part_is_allowed
from app.services.acl import require_items_view
from app.services.audit import log_action
from app.services.field_config import context_field_ids, get_field_config, resolve_part_field_values
from app.services.part_norm import clean_rev

bp = Blueprint("bom_tree_api", __name__, url_prefix="/api")

def _clean_rev(value: object) -> str:
    return clean_rev(value)

def _has_children(pn: str, rev: str | None = None) -> bool:
    if "parent_pn" in BOMLink._fields:
        if rev is not None and "parent_rev" in BOMLink._fields:
            return BOMLink.objects(parent_pn=pn, parent_rev=_clean_rev(rev)).limit(1).count() > 0
        return BOMLink.objects(parent_pn=pn).limit(1).count() > 0
    p = Part.objects(part_number=pn).only("id").first()
    if not p:
        return False
    return BOMLink.objects(parent=p).limit(1).count() > 0


def _coverage_groups(pn: str, rev: str) -> set[str]:
    groups: set[str] = set()
    for row in PartFile.objects(part_number__iexact=pn, revision__iexact=_clean_rev(rev)).only("ext_group"):
        if row.ext_group:
            groups.add(str(row.ext_group).lower())
    return groups

def _node(pn: str, link=None, rev: str | None = None, config: dict | None = None):
    # Prefer specific revision when provided, else pick latest by updated_at
    rev_clean = _clean_rev(rev) if rev is not None else None
    if rev is not None:
        p = Part.objects(part_number=pn, revision=rev_clean).first()
    else:
        p = Part.objects(part_number=pn).order_by("-updated_at").first()
    attrs = harvest_part_attrs(p) if p else {}
    effective_rev = _clean_rev(attrs.get("revision") or (p.revision if p else "") or (rev_clean or ""))
    proc_label = _process_label(attrs)
    config = config or get_field_config()
    thumbs = preview_png_urls_for(pn, effective_rev)
    coverage = _coverage_groups(pn, effective_rev)
    values = resolve_part_field_values(
        p,
        context_field_ids("bom_tree", config),
        attrs=attrs,
        config=config,
        extra={
            "part_number": pn,
            "revision": effective_rev,
            "description": attrs.get("description", ""),
            "qty": getattr(link, "qty", None),
            "uom": getattr(link, "uom", None),
            "alt_group": getattr(link, "alt_group", "") or "",
            "thumbnail": thumbs[0] if thumbs else "",
        },
        coverage=coverage,
    )
    return {
        "key": f"{pn}::{effective_rev}",
        "leaf": not _has_children(pn, effective_rev),
        "data": {
            "pn": pn,
            "desc": attrs.get("description",""),
            "rev":  effective_rev,
            "qty":  getattr(link,"qty",None),
            "uom":  getattr(link,"uom",None),
            "alt_group": getattr(link,"alt_group","") or "",
            "material":  attrs.get("material",""),
            "finish":    attrs.get("finish",""),
            "process":   proc_label,
            "thumb_urls": thumbs,
            "attrs": attrs,
            **values,
        }
    }


def _process_label(attrs: dict) -> str:
    if not isinstance(attrs, dict):
        return ""
    raw = []
    procs = attrs.get("processes", [])
    if isinstance(procs, (list, tuple)):
        raw.extend(list(procs))
    for key in ("process", "process2", "process3"):
        val = attrs.get(key)
        if val:
            raw.append(val)
    seen = set()
    out = []
    for item in raw:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return ", ".join(out)

def _is_hardware_node(node: dict) -> bool:
    try:
        attrs = (node.get("data") or {}).get("attrs") or {}
        meta = current_app.config.get("PROCESS_META", {}) or {}
        procs = normalize_processes(attrs, meta)
        return "hardware" in procs
    except Exception:
        return False

@bp.get("/bom_tree")
@login_required
@require_items_view
def bom_tree():
    config = get_field_config()
    pn = (request.args.get("pn") or "").strip()
    rev = request.args.get("rev")  # keep None vs ""
    parent = (request.args.get("parent") or "").strip()
    parent_rev = request.args.get("parent_rev")
    parent_rev = request.args.get("parent_rev")

    if pn:
        # Build root node for specific revision if provided; else latest
        if rev is not None:
            p = Part.objects(part_number=pn, revision=_clean_rev(rev)).first()
        else:
            p = Part.objects(part_number=pn).order_by("-updated_at").first()
        if not p:
            return jsonify([])
        # ACL: root must be allowed if enforcement active
        try:
            allowed = allowed_parts_for(current_user)
            if isinstance(allowed, set) and not part_is_allowed(allowed, p.part_number, p.revision or ""):
                return jsonify([]), 403
        except Exception:
            pass
        root_rev = _clean_rev(rev) if rev is not None else _clean_rev(p.revision or "")
        root = _node(p.part_number, rev=(root_rev if rev is not None else root_rev), config=config)
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
                links = BOMLink.objects(parent_pn=parent, parent_rev=_clean_rev(parent_rev)).only("child_pn","qty","uom","alt_group","child_rev")
            else:
                links = BOMLink.objects(parent_pn=parent).only("child_pn","qty","uom","alt_group","child_rev")
            kids = []
            for l in links:
                child_pn = getattr(l, "child_pn", None)
                if child_pn and child_pn != parent:
                    c_rev = _clean_rev(getattr(l, "child_rev", None)) if hasattr(l, "child_rev") else None
                    # ACL filter per child if enforced
                    try:
                        allowed = allowed_parts_for(current_user)
                        if isinstance(allowed, set) and not part_is_allowed(allowed, child_pn, c_rev or ""):
                            continue
                    except Exception:
                        pass
                    kids.append(_node(child_pn, l, rev=c_rev, config=config))
            try:
                log_action("bom.view", resource_type="bom", resource=f"children:{parent}:{(parent_rev or '')}")
            except Exception:
                pass
            kids.sort(key=lambda n: 1 if _is_hardware_node(n) else 0)
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
                    try:
                        allowed = allowed_parts_for(current_user)
                        if isinstance(allowed, set) and not part_is_allowed(allowed, child_pn, ""):
                            continue
                    except Exception:
                        pass
                    kids.append(_node(child_pn, l, config=config))
            try:
                log_action("bom.view", resource_type="bom", resource=f"children:{parent}")
            except Exception:
                pass
            kids.sort(key=lambda n: 1 if _is_hardware_node(n) else 0)
            return jsonify(kids)

    return jsonify([])
