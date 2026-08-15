# app/views/whereused.py
from flask import Blueprint, request, jsonify
from flask_login import login_required
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
from flask_login import current_user
from app.services.authorization import (
    authorised_part_pairs,
    has_permission,
    require_permission,
    scope_queryset,
)
from app.services.field_policies import (
    allowed_read_fields,
    filter_response_fields,
    response_context,
)
from app.services.file_security import managed_file_group_allowed
from app.services.part_norm import clean_rev

bp = Blueprint("whereused_api", __name__, url_prefix="/api")

def _resolve_scoped_revision(pn: str, revision: object, user=None) -> str:
    revision_clean = clean_rev(revision)
    if revision_clean:
        return revision_clean
    query = Part.objects(part_number__iexact=str(pn or "").strip())
    if user is not None:
        query = scope_queryset(query, user, "parts")
    part = query.order_by("-updated_at").first()
    if not part:
        return ""
    attrs = harvest_part_attrs(part)
    return clean_rev(attrs.get("revision") or part.revision or "")


def _coverage_groups(pn: str, rev: str) -> set[str]:
    if not has_permission(current_user, "files.read"):
        return set()
    groups: set[str] = set()
    for row in PartFile.objects(part_number__iexact=pn, revision__iexact=clean_rev(rev)).only("ext_group"):
        if row.ext_group and managed_file_group_allowed(current_user, row.ext_group):
            groups.add(str(row.ext_group).lower())
    return groups

def _rows_for_child_pn(
    pn: str,
    child_rev: str | None = None,
    *,
    config: dict | None = None,
    user=None,
):
    """Return where-used rows for a child part number, keeping revisions accurate."""
    config = config or get_field_config()
    # Fetch links where this PN is the child
    if "child_pn" in BOMLink._fields:
        query = BOMLink.objects(child_pn=pn)
        links = list(query)
    else:
        child_part = Part.objects(part_number=pn).only("id").first()
        links = list(BOMLink.objects(child=child_part))

    requested_child_rev = _resolve_scoped_revision(pn, child_rev, user)
    normalized_links = []
    for link in links:
        if "parent_pn" in BOMLink._fields:
            parent_pn = str(getattr(link, "parent_pn", None) or "").strip()
            parent_rev = _resolve_scoped_revision(
                parent_pn,
                getattr(link, "parent_rev", ""),
                user,
            )
            effective_child_rev = _resolve_scoped_revision(
                pn,
                getattr(link, "child_rev", ""),
                user,
            )
        else:
            parent_obj = getattr(link, "parent", None)
            parent_pn = str(getattr(parent_obj, "part_number", None) or "").strip()
            parent_rev = _resolve_scoped_revision(
                parent_pn,
                getattr(parent_obj, "revision", "") if parent_obj else "",
                user,
            )
            effective_child_rev = requested_child_rev
        if not parent_pn:
            continue
        if (
            child_rev is not None
            and effective_child_rev.casefold() != requested_child_rev.casefold()
        ):
            continue
        normalized_links.append(
            (link, parent_pn, parent_rev, effective_child_rev)
        )

    allowed_pairs = None
    if user is not None:
        requested_pairs = []
        for _, parent_pn, parent_rev, effective_child_rev in normalized_links:
            requested_pairs.append((pn, effective_child_rev))
            requested_pairs.append((parent_pn, parent_rev))
        allowed_pairs = authorised_part_pairs(user, requested_pairs)

    rows = []
    seen = set()
    for l, parent_pn, parent_rev, effective_child_rev in normalized_links:
        if allowed_pairs is not None:
            child_key = (pn.casefold(), effective_child_rev.casefold())
            parent_key = (parent_pn.casefold(), parent_rev.casefold())
            if child_key not in allowed_pairs or parent_key not in allowed_pairs:
                continue

        # Keep distinct rows per PN/REV combination
        key = (parent_pn, parent_rev or "", effective_child_rev or "")
        if key in seen:
            continue
        seen.add(key)

        # Prefer the exact revision from the link; no cross-rev fallback
        parent_query = Part.objects
        if user is not None:
            parent_query = scope_queryset(parent_query, user, "parts")
        parent_part = parent_query.filter(
            part_number__iexact=parent_pn,
            revision__iexact=(parent_rev or ""),
        ).first()
        if not parent_part:
            continue
        attrs = harvest_part_attrs(parent_part) if parent_part else {}
        resolved_parent_rev = clean_rev(attrs.get("revision", "") or parent_rev or "")
        thumbs = (
            thumb_urls_for(parent_pn, resolved_parent_rev, user=user)
            if user is not None and has_permission(user, "files.read")
            else []
        )
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
@require_permission("bom.read")
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
    custom_field_ids = {
        str(field.get("id") or "").strip()
        for field in config.get("fields") or []
        if isinstance(field, dict)
        and field.get("kind") == "custom"
        and str(field.get("id") or "").strip()
    }
    visible_fields = allowed_read_fields(
        "whereused",
        current_user,
        context={
            "surface": "list",
            "configured_fields": custom_field_ids,
        },
    )

    rows = _rows_for_child_pn(pn, rev, config=config, user=current_user)

    filterable_ids = set(context_field_ids("where_used", config)) & visible_fields
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

    total = len(rows)
    boundary = response_context("parts", current_user)
    page = [
        filter_response_fields(
            "whereused",
            current_user,
            row,
            context={
                "policy_context": boundary,
                "surface": "list",
                "configured_fields": custom_field_ids,
            },
        )
        for row in rows[first:first+rows_per_page]
    ]
    return jsonify({"data": page, "totalRecords": total})
