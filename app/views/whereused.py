# app/views/whereused.py
from flask import Blueprint, request, jsonify
from flask_login import login_required
from app.services.acl import require_items_view
from app.services.audit import log_action
from app.models.part import Part
from app.models.bom import BOMLink
from app.services.thumbs import thumb_urls_for
from app.services.attrs import harvest_part_attrs
from flask_login import login_required, current_user
from app.services.acl import require_items_view, allowed_parts_for

bp = Blueprint("whereused_api", __name__, url_prefix="/api")

def _rows_for_child_pn(pn: str, child_rev: str | None = None):
    """Return where-used rows for a child part number, keeping revisions accurate."""
    # Fetch links where this PN is the child
    if "child_pn" in BOMLink._fields:
        query = BOMLink.objects(child_pn=pn)
        if child_rev is not None and "child_rev" in BOMLink._fields:
            query = query.filter(child_rev=(child_rev or ""))
        links = query
    else:
        child_part = Part.objects(part_number=pn).only("id").first()
        links = BOMLink.objects(child=child_part)

    rows = []
    seen = set()
    for l in links:
        # Resolve parent PN / REV
        if "parent_pn" in BOMLink._fields:
            parent_pn = getattr(l, "parent_pn", None)
            parent_rev = getattr(l, "parent_rev", "") if hasattr(l, "parent_rev") else ""
            effective_child_rev = getattr(l, "child_rev", "") if hasattr(l, "child_rev") else (child_rev or "")
        else:
            parent_obj = getattr(l, "parent", None)
            parent_pn = getattr(parent_obj, "part_number", None)
            parent_rev = getattr(parent_obj, "revision", "") if parent_obj else ""
            effective_child_rev = child_rev or ""

        if not parent_pn:
            continue

        # Keep distinct rows per PN/REV combination
        key = (parent_pn, parent_rev or "", effective_child_rev or "")
        if key in seen:
            continue
        seen.add(key)

        # Prefer the exact revision from the link; fall back to latest if missing
        parent_part = Part.objects(part_number=parent_pn, revision=(parent_rev or "")).first() or \
                      Part.objects(part_number=parent_pn).order_by("-updated_at").first()
        attrs = harvest_part_attrs(parent_part) if parent_part else {}
        resolved_parent_rev = attrs.get("revision", "") or parent_rev or ""

        rows.append({
            "id": f"{parent_pn}::{resolved_parent_rev}::{pn}::{effective_child_rev}",
            "parent_pn": parent_pn,
            "parent_desc": attrs.get("description", "") or getattr(parent_part, "description", "") or "",
            "qty": getattr(l, "qty", None),
            "uom": getattr(l, "uom", "") or "",
            "alt_group": getattr(l, "alt_group", "") or "",
            "parent_thumb_urls": thumb_urls_for(parent_pn, (resolved_parent_rev or None)),
            "parent_rev": resolved_parent_rev,
            "child_pn": pn,
            "child_rev": (effective_child_rev or ""),
        })
    return rows

@bp.post("/whereused_lazy")
@login_required
@require_items_view
def whereused_lazy():
    p = request.get_json(silent=True) or {}
    pn = (p.get("pn") or "").strip()
    rev = p.get("rev")  # keep None vs ""
    first = int(p.get("first") or 0)
    rows_per_page = int(p.get("rows") or 25)
    sort_field = (p.get("sortField") or "parent_pn")
    sort_order = int(p.get("sortOrder") or 1)
    filters = p.get("filters") or {}

    rows = _rows_for_child_pn(pn, rev)

    # filters (contains)
    def contains(val, needle):
        return (needle or "").lower() in (str(val or "")).lower()

    fp = (filters.get("parent_pn", {}) or {}).get("value")
    fd = (filters.get("parent_desc", {}) or {}).get("value")
    fa = (filters.get("alt_group", {}) or {}).get("value")
    if fp: rows = [r for r in rows if contains(r["parent_pn"], fp)]
    if fd: rows = [r for r in rows if contains(r["parent_desc"], fd)]
    if fa: rows = [r for r in rows if contains(r["alt_group"], fa)]

    # sort
    reverse = (sort_order == -1)
    if sort_field in ("parent_pn", "parent_desc", "alt_group", "uom"):
        rows.sort(key=lambda r: (r.get(sort_field) or "").lower(), reverse=reverse)
    elif sort_field == "qty":
        rows.sort(key=lambda r: (r.get("qty") or 0), reverse=reverse)

    # ACL: filter rows by whether parent is allowed (if enforced)
    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set):
            rows = [r for r in rows if (r.get("parent_pn"), (r.get("parent_rev") or "")) in allowed]
    except Exception:
        pass
    total = len(rows)
    page = rows[first:first+rows_per_page]
    try:
        log_action("whereused.view", resource_type="whereused", resource=f"{pn}:{rev or ''}")
    except Exception:
        pass
    return jsonify({"data": page, "totalRecords": total})
