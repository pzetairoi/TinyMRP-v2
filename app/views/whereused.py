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
    """Return where-used rows for a child part number, tolerant of both link schemas.

    child_rev is accepted for consistency with the rest of the PN+REV-aware API.
    Current BOMLink schema does not encode child revision, so this value is informational.
    """
    # Fetch links where this PN is the child
    if "child_pn" in BOMLink._fields:
        links = BOMLink.objects(child_pn=pn)
    else:
        child_part = Part.objects(part_number=pn).only("id").first()
        links = BOMLink.objects(child=child_part)

    rows = []
    for l in links:
        # Resolve parent PN
        if "parent_pn" in BOMLink._fields:
            parent_pn = getattr(l, "parent_pn", None)
        else:
            parent_obj = getattr(l, "parent", None)
            parent_pn = getattr(parent_obj, "part_number", None)

        if not parent_pn:
            continue

        # Always prefer the latest known revision of the parent for attrs/desc
        parent_part = Part.objects(part_number=parent_pn).order_by("-updated_at").first()
        attrs = harvest_part_attrs(parent_part) if parent_part else {}
        parent_rev = attrs.get("revision", "")

        rows.append({
            "parent_pn": parent_pn,
            "parent_desc": attrs.get("description", "") or getattr(parent_part, "description", "") or "",
            "qty": getattr(l, "qty", None),
            "uom": getattr(l, "uom", "") or "",
            "alt_group": getattr(l, "alt_group", "") or "",
            "parent_thumb_urls": thumb_urls_for(parent_pn, (parent_rev or None)),
            "parent_rev": parent_rev,
            "child_pn": pn,
            "child_rev": (child_rev or ""),
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
