# app/views/whereused.py
from flask import Blueprint, request, jsonify
from flask_login import login_required
from app.services.acl import require_items_view
from app.services.audit import log_action
from app.models.artifact import PartFile
from app.models.part import Part
from app.models.bom import BOMLink
from app.services.thumbs import thumb_urls_for
from app.services.attrs import harvest_part_attrs
from app.services.field_config import (
    context_field_ids,
    field_index,
    get_field_config,
    matches_field_filter_value,
    resolve_part_field_values,
)
from flask_login import login_required, current_user
from app.services.acl import require_items_view, allowed_parts_for, part_is_allowed
from app.services.part_norm import clean_rev

bp = Blueprint("whereused_api", __name__, url_prefix="/api")

def _clean_rev(value: object) -> str:
    return clean_rev(value)


def _coverage_groups(pn: str, rev: str) -> set[str]:
    groups: set[str] = set()
    for row in PartFile.objects(part_number__iexact=pn, revision__iexact=_clean_rev(rev)).only("ext_group"):
        if row.ext_group:
            groups.add(str(row.ext_group).lower())
    return groups

def _rows_for_child_pn(pn: str, child_rev: str | None = None, *, config: dict | None = None):
    """Return where-used rows for a child part number, keeping revisions accurate."""
    config = config or get_field_config()
    # Fetch links where this PN is the child
    if "child_pn" in BOMLink._fields:
        query = BOMLink.objects(child_pn=pn)
        if child_rev is not None and "child_rev" in BOMLink._fields:
            query = query.filter(child_rev=_clean_rev(child_rev))
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
            parent_rev = _clean_rev(getattr(l, "parent_rev", "") if hasattr(l, "parent_rev") else "")
            effective_child_rev = _clean_rev(getattr(l, "child_rev", "") if hasattr(l, "child_rev") else (child_rev or ""))
        else:
            parent_obj = getattr(l, "parent", None)
            parent_pn = getattr(parent_obj, "part_number", None)
            parent_rev = _clean_rev(getattr(parent_obj, "revision", "") if parent_obj else "")
            effective_child_rev = _clean_rev(child_rev or "")

        if not parent_pn:
            continue

        # Keep distinct rows per PN/REV combination
        key = (parent_pn, parent_rev or "", effective_child_rev or "")
        if key in seen:
            continue
        seen.add(key)

        # Prefer the exact revision from the link; no cross-rev fallback
        parent_part = Part.objects(part_number=parent_pn, revision=(parent_rev or "")).first()
        attrs = harvest_part_attrs(parent_part) if parent_part else {}
        resolved_parent_rev = _clean_rev(attrs.get("revision", "") or parent_rev or "")
        thumbs = thumb_urls_for(parent_pn, resolved_parent_rev)
        coverage = _coverage_groups(parent_pn, resolved_parent_rev)
        values = resolve_part_field_values(
            parent_part,
            context_field_ids("where_used", config),
            attrs=attrs,
            config=config,
            extra={
                "part_number": parent_pn,
                "revision": resolved_parent_rev,
                "description": attrs.get("description", "") or getattr(parent_part, "description", "") or "",
                "qty": getattr(l, "qty", None),
                "uom": getattr(l, "uom", "") or "",
                "alt_group": getattr(l, "alt_group", "") or "",
                "thumbnail": thumbs[0] if thumbs else "",
            },
            coverage=coverage,
        )

        rows.append({
            "id": f"{parent_pn}::{resolved_parent_rev}::{pn}::{effective_child_rev}",
            "parent_pn": values.get("part_number", parent_pn),
            "parent_desc": values.get("description", attrs.get("description", "") or getattr(parent_part, "description", "") or ""),
            "qty": getattr(l, "qty", None),
            "uom": getattr(l, "uom", "") or "",
            "alt_group": getattr(l, "alt_group", "") or "",
            "parent_thumb_urls": thumbs,
            "parent_rev": values.get("revision", resolved_parent_rev),
            "child_pn": pn,
            "child_rev": (effective_child_rev or ""),
            "part_number": values.get("part_number", parent_pn),
            "revision": values.get("revision", resolved_parent_rev),
            "description": values.get("description", attrs.get("description", "") or getattr(parent_part, "description", "") or ""),
            **values,
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
    sort_field = (p.get("sortField") or "part_number")
    sort_order = int(p.get("sortOrder") or 1)
    filters = p.get("filters") or {}
    config = get_field_config()

    rows = _rows_for_child_pn(pn, rev, config=config)

    filterable_ids = set(context_field_ids("where_used", config))
    field_meta = field_index(config)
    alias_map = {"parent_pn": "part_number", "parent_rev": "revision", "parent_desc": "description"}
    for raw_key, payload in filters.items():
        field_id = alias_map.get(raw_key, raw_key)
        if field_id not in filterable_ids:
            continue
        value = (payload or {}).get("value")
        if value in (None, ""):
            continue
        data_type = str((field_meta.get(field_id) or {}).get("data_type") or "text")
        rows = [r for r in rows if matches_field_filter_value(r.get(field_id), value, data_type)]

    # sort
    reverse = (sort_order == -1)
    sort_field = alias_map.get(sort_field, sort_field)
    sort_type = str((field_meta.get(sort_field) or {}).get("data_type") or "text")
    if sort_type == "number" or sort_field in {"qty"}:
        rows.sort(key=lambda r: (r.get(sort_field) or 0), reverse=reverse)
    else:
        rows.sort(key=lambda r: (str(r.get(sort_field) or "")).lower(), reverse=reverse)

    # ACL: filter rows by whether parent is allowed (if enforced)
    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set):
            rows = [r for r in rows if part_is_allowed(allowed, r.get("part_number"), r.get("revision") or "")]
    except Exception:
        pass
    total = len(rows)
    page = rows[first:first+rows_per_page]
    try:
        log_action("whereused.view", resource_type="whereused", resource=f"{pn}:{rev or ''}")
    except Exception:
        pass
    return jsonify({"data": page, "totalRecords": total})
