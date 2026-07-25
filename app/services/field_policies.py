"""Minimum sensitive-field policies for authenticated JSON responses.

Object scope is enforced by :mod:`app.services.authorization`.  This module
only removes sensitive properties after a scoped object has been serialized.
Anonymous public-share responses deliberately use their separate stricter
serializer.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from copy import deepcopy
from typing import Any


_logger = logging.getLogger("tinymrp.field_policies")

_ALIASES = {
    "part": "parts",
    "bom": "bom_line",
    "file": "file_metadata",
    "files": "file_metadata",
    "job": "jobs",
    "order": "orders",
    "customer": "customers",
    "supplier": "suppliers",
}
_PARENT = {
    "parts": "parts",
    "bom_line": "parts",
    "file_metadata": "parts",
    "comment": "parts",
    "profile": "parts",
    "part_dashboard": "parts",
    "part_insight": "parts",
    "whereused": "parts",
    "job_order_summary": "parts",
    "jobs": "jobs",
    "job_stage": "jobs",
    "job_bom_line": "jobs",
    "job_bom_admin_line": "jobs",
    "job_stats": "jobs",
    "orders": "orders",
    "order_line": "orders",
    "order_reference": "orders",
    "order_stats": "orders",
    "order_mutation": "orders",
    "customers": "customers",
    "customer_order": "customers",
    "customer_stats": "customers",
    "suppliers": "suppliers",
    "supplier_order": "suppliers",
    "supplier_stats": "suppliers",
    "address": "customers",
    "contact": "customers",
}
_READ_PERMISSION = {
    "parts": "parts.read",
    "jobs": "jobs.read",
    "orders": "orders.read",
    "customers": "customers.read",
    "suppliers": "suppliers.read",
}

_PART_BASE = frozenset(
    """
    id key row_key part_number pn revision rev display_code description desc
    status category uom qty total_qty alt_group leaf children level material
    finish mass process processes manufacturer mfr_part thumb_urls thumbnail
    has_pdf has_png has_dxf has_step has_edr has_3mf has_ply has_stl
    has_datasheet datasheet field_values classification processes_normalized
    missing_fields deliverables_present deliverables_missing_recommended
    where_used_count total_qty_used
    """.split()
)
_PART_EXTERNAL = _PART_BASE - frozenset(
    {
        "mass",
        "manufacturer",
        "mfr_part",
        "field_values",
        "classification",
        "processes_normalized",
        "missing_fields",
        "deliverables_present",
        "deliverables_missing_recommended",
        "where_used_count",
        "total_qty_used",
    }
)
_PART_OPERATOR = _PART_EXTERNAL - frozenset({"has_datasheet", "datasheet"})
_PART_INTERNAL_SEARCH = _PART_BASE | frozenset(
    """
    attributes attrs notes comments uploader_profile approver_profile approved
    approved_date approved_by pending_review_count pending_review_severity
    has_pending_reviews whereused other_versions jobs_orders parent_pn parent_rev
    parent_desc parent_thumb_urls child_pn child_rev immediate_pn immediate_rev
    immediate_desc top_pn top_rev top_desc parent_part_number parent_revision
    parent_description source job_number order_number order_kind order_status
    """.split()
)

_JOB_EXTERNAL = frozenset(
    """
    job_number title description part_number part_revision qty_ordered
    qty_produced status priority scheduled_start scheduled_start_display
    scheduled_end scheduled_end_display bom
    """.split()
)
_JOB_OPERATOR = _JOB_EXTERNAL | frozenset(
    {"qty_scrapped", "material_reserved", "stages", "order_number"}
)
_STAGE_SAFE = frozenset(
    """
    stage_id name sequence status started_at started_at_display completed_at
    completed_at_display
    """.split()
)
_STAGE_OPERATIONAL = frozenset(
    {"assigned_to", "department", "estimated_hours", "actual_hours", "note"}
)
_JOB_BOM_SAFE = frozenset({"pn", "part_number", "rev", "revision", "qty"})

_ORDER_EXTERNAL = frozenset(
    """
    order_number kind description status job customer_po order_date
    order_date_display requested_delivery requested_delivery_display
    job_required_qty total_ordered_for_job promised_delivery
    promised_delivery_display actual_delivery actual_delivery_display
    shipping_method carrier tracking_number lines
    """.split()
)
_ORDER_FINANCIAL = frozenset(
    {"subtotal", "tax_amount", "shipping_cost", "discount_amount", "total", "currency"}
)
_ORDER_REVIEW = frozenset(
    """
    approved_by approved_at approved_at_display rejection_reason created_at
    created_at_display updated_at updated_at_display
    """.split()
)
_ORDER_LINE_SAFE = frozenset(
    """
    pn part_number rev revision qty uom description qty_shipped qty_received
    requested_delivery requested_delivery_display
    """.split()
)
_ORDER_LINE_FINANCIAL = frozenset(
    {"unit_price", "discount_pct", "tax_pct", "line_total"}
)

_CUSTOMER_EXTERNAL = frozenset(
    """
    code name description is_company status primary_contact email website phone
    shipping_addresses default_shipping_label
    """.split()
)
_CUSTOMER_FINANCIAL = frozenset(
    """
    customer_type segment billing_address tax_id payment_terms credit_limit
    discount_pct currency sales_rep industry
    """.split()
)
_SUPPLIER_EXTERNAL = frozenset(
    """
    code name description status categories primary_contact email phone website
    lead_time_days address
    """.split()
)
_SUPPLIER_FINANCIAL = frozenset(
    {"rating", "tax_id", "payment_terms", "currency", "min_order_value", "billing_address"}
)

_FILE_SAFE = frozenset(
    """
    name filename display_name category ext_group ext size mtime mtime_iso
    modified_at uploaded_at url urls image_urls preview_url thumbnail_url
    preview_available thumbnail_available revision is_dwg mime content_type
    label kind part_number display_revision recorded_at recorded_at_display
    recorded_at_local
    """.split()
)
_ADDRESS_SAFE = frozenset(
    {"label", "line1", "line2", "city", "state", "postal", "country", "is_default"}
)
_CONTACT_SAFE = frozenset({"name", "title", "email", "phone", "is_primary"})
_PROFILE_SAFE = frozenset(
    {"display_name", "label", "initials", "avatar_color", "avatar_shape", "avatar_url"}
)
_COMMENT_SAFE = frozenset(
    """
    id ts ts_display ts_local text status priority resolved_at replies reply_count
    author_display author_profile
    """.split()
)
_SENSITIVE_CUSTOM_PARTS = (
    "token",
    "secret",
    "password",
    "credential",
    "private_key",
    "api_key",
    "storage",
    "mount",
    "path",
)
_ALWAYS_INTERNAL_DENIED = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "token_hash",
        "secret",
        "api_key",
        "private_key",
        "storage_path",
        "mount_path",
        "rel_path",
        "path",
        "sha256",
        "audit_meta",
        "audit_internal",
    }
)
_AUTOCOMPLETE = {
    "parts": frozenset(
        {"part_number", "pn", "revision", "rev", "display_code", "description", "desc", "status"}
    ),
    "jobs": frozenset({"job_number", "title", "status", "part_number", "part_revision"}),
    "orders": frozenset({"order_number", "description", "kind", "status"}),
    "customers": frozenset({"code", "name", "status"}),
    "suppliers": frozenset({"code", "name", "status"}),
}


def _normalise(resource_type: str) -> str:
    value = str(resource_type or "").strip().lower()
    return _ALIASES.get(value, value)


def _has(user: Any, permission: str) -> bool:
    try:
        from app.services.authorization import has_permission

        return has_permission(user, permission)
    except Exception:
        return False


def response_context(
    resource_type: str,
    user: Any,
    *,
    context: Mapping[str, Any] | None = None,
) -> str:
    """Resolve the effective internal, portal, or assigned-job boundary."""

    if isinstance(context, Mapping):
        explicit = str(
            context.get("policy_context")
            or context.get("boundary")
            or context.get("audience")
            or ""
        ).strip()
        if explicit in {
            "internal",
            "customer_portal",
            "supplier_portal",
            "production_operator",
        }:
            return explicit
    normalized = _normalise(resource_type)
    parent = _PARENT.get(normalized)
    permission = _READ_PERMISSION.get(parent or "")
    if not parent or not permission:
        return ""
    try:
        from app.services.authorization import permission_scope_modes

        modes = permission_scope_modes(user, permission, resource_type=parent)
    except Exception:
        return ""
    if "global" in modes or modes & {"purchase", "sales"}:
        return "internal"
    if "customer" in modes:
        return "customer_portal"
    if "supplier" in modes:
        return "supplier_portal"
    if "assigned" in modes:
        return "production_operator"
    return ""


def _external_fields(normalized: str, boundary: str) -> frozenset[str]:
    part_fields = _PART_OPERATOR if boundary == "production_operator" else _PART_EXTERNAL
    order_fields = _ORDER_EXTERNAL
    if boundary == "customer_portal":
        order_fields |= {"customer"}
    elif boundary == "supplier_portal":
        order_fields |= {"supplier"}
    policies = {
        "parts": part_fields,
        "bom_line": part_fields,
        "part_insight": part_fields,
        "file_metadata": _FILE_SAFE,
        "jobs": _JOB_OPERATOR if boundary == "production_operator" else _JOB_EXTERNAL,
        "job_stage": (
            _STAGE_SAFE | _STAGE_OPERATIONAL
            if boundary == "production_operator"
            else _STAGE_SAFE
        ),
        "job_bom_line": _JOB_BOM_SAFE,
        "orders": order_fields,
        "order_line": _ORDER_LINE_SAFE,
        "customers": _CUSTOMER_EXTERNAL if boundary == "customer_portal" else frozenset(),
        "suppliers": _SUPPLIER_EXTERNAL if boundary == "supplier_portal" else frozenset(),
        "address": _ADDRESS_SAFE,
        "contact": frozenset(),
        "comment": frozenset(),
        "profile": frozenset(),
        "job_stats": frozenset({"ok", "status_counts", "overdue", "active"}),
        "order_stats": frozenset({"ok", "status_counts"}),
        "order_mutation": frozenset({"ok", "removed"}),
        "customer_order": frozenset({"order_number", "status", "order_date"}),
        "supplier_order": frozenset({"order_number", "status", "order_date"}),
        "customer_stats": frozenset({"ok", "orders_count", "last_order_date"}),
        "supplier_stats": frozenset({"ok", "on_time_rate", "avg_lead_days", "orders_count"}),
        "part_dashboard": frozenset({"counts", "recent_parts", "top_hardware"}),
    }
    if normalized == "whereused":
        return part_fields | frozenset(
            """
            parent_pn parent_rev parent_desc parent_thumb_urls child_pn child_rev
            immediate_pn immediate_rev immediate_desc top_pn top_rev top_desc
            parent_part_number parent_revision parent_description qty
            """.split()
        )
    return policies.get(normalized, frozenset())


def _configured_fields(user: Any, context: Mapping[str, Any] | None) -> frozenset[str]:
    if not isinstance(context, Mapping) or not (
        _has(user, "parts.update") or _has(user, "bom.update")
    ):
        return frozenset()
    return frozenset(
        value
        for raw in context.get("configured_fields") or ()
        for value in [str(raw or "").strip()]
        if value
        and not any(part in value.lower() for part in _SENSITIVE_CUSTOM_PARTS)
    )


def allowed_read_fields(
    resource_type: str,
    user: Any,
    *,
    context: Mapping[str, Any] | None = None,
) -> frozenset[str]:
    """Return fields safe for search/sort discovery at the active boundary."""

    normalized = _normalise(resource_type)
    if normalized not in _PARENT:
        return frozenset()
    boundary = response_context(normalized, user, context=context)
    if not boundary:
        return frozenset()
    if boundary == "internal":
        fields = _PART_INTERNAL_SEARCH if normalized in {
            "parts",
            "bom_line",
            "part_insight",
            "whereused",
        } else frozenset()
        fields |= _configured_fields(user, context)
    else:
        fields = _external_fields(normalized, boundary)
    if isinstance(context, Mapping) and context.get("surface") == "autocomplete":
        fields &= _AUTOCOMPLETE.get(normalized, frozenset())
    return fields


def _internal_fields(
    normalized: str,
    user: Any,
    payload: Mapping[str, Any],
    context: Mapping[str, Any] | None,
) -> frozenset[str]:
    fields = {
        key
        for key in set(payload) - _ALWAYS_INTERNAL_DENIED
        if not any(
            part in str(key or "").strip().lower()
            for part in _SENSITIVE_CUSTOM_PARTS
        )
    }
    if normalized == "file_metadata":
        fields &= _FILE_SAFE
        if (
            isinstance(context, Mapping)
            and context.get("markup_source")
            and (_has(user, "markups.read") or _has(user, "markups.write"))
        ):
            fields |= {"id", "source_file_id", "source_fingerprint"}
    elif normalized == "profile":
        fields &= _PROFILE_SAFE
    elif normalized == "comment":
        fields &= _COMMENT_SAFE if _has(user, "comments.read") else set()
    elif normalized == "address":
        fields &= _ADDRESS_SAFE
    elif normalized == "contact":
        fields &= _CONTACT_SAFE
    elif normalized in {"parts", "bom_line", "part_insight", "whereused"}:
        fields -= {"internal_cost", "cost", "unit_cost", "margin", "gross_margin"}
        if not _has(user, "comments.read"):
            fields -= {
                "notes",
                "comments",
                "pending_review_count",
                "pending_review_severity",
                "has_pending_reviews",
            }
        if not (_has(user, "markups.read") or _has(user, "markups.write")):
            fields.discard("uploader_profile")
        if not (_has(user, "reviews.approve") or _has(user, "audit.read")):
            fields -= {"approver_profile", "approved", "approved_date", "approved_by"}
    elif normalized == "jobs":
        fields -= {"customer_id", "vendor_ids", "participant_ids"}
        if not _has(user, "customers.read"):
            fields.discard("customer")
        if not _has(user, "orders.read"):
            fields.discard("order_number")
    elif normalized == "orders":
        fields -= {"customer_id", "supplier_id", "job_id"}
        if not _has(user, "orders.financial.read"):
            fields -= _ORDER_FINANCIAL
        if not _has(user, "customers.read"):
            fields.discard("customer")
        if not _has(user, "suppliers.read"):
            fields.discard("supplier")
        if not _has(user, "jobs.read"):
            fields.discard("job")
        if not (_has(user, "orders.approve") or _has(user, "audit.read")):
            fields -= _ORDER_REVIEW
    elif normalized == "order_line" and not _has(user, "orders.financial.read"):
        fields -= _ORDER_LINE_FINANCIAL
    elif normalized == "customers" and not _has(user, "customers.financial.read"):
        fields -= _CUSTOMER_FINANCIAL
    elif normalized == "suppliers" and not _has(user, "suppliers.financial.read"):
        fields -= _SUPPLIER_FINANCIAL
    elif normalized in {"order_stats", "order_mutation", "customer_order", "supplier_order"}:
        if not _has(user, "orders.financial.read"):
            fields -= {"revenue_month", "avg_order_value", "total"}
    elif normalized == "customer_stats" and not _has(user, "orders.financial.read"):
        fields.discard("total_revenue")
    return frozenset(fields)


def filter_response_fields(
    resource_type: str,
    user: Any,
    payload: Mapping[str, Any],
    *,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Copy a scoped response and remove sensitive properties; errors deny."""

    if not isinstance(payload, Mapping):
        return {}
    try:
        normalized = _normalise(resource_type)
        if normalized not in _PARENT:
            return {}
        boundary = response_context(normalized, user, context=context)
        if not boundary:
            return {}
        if boundary == "internal":
            allowed = _internal_fields(normalized, user, payload, context)
        else:
            allowed = _external_fields(normalized, boundary)
        if isinstance(context, Mapping) and context.get("surface") == "autocomplete":
            allowed &= _AUTOCOMPLETE.get(normalized, frozenset())
        result = {key: deepcopy(value) for key, value in payload.items() if key in allowed}
        field_values = result.get("field_values")
        if isinstance(field_values, Mapping):
            result["field_values"] = {
                str(key): deepcopy(value)
                for key, value in field_values.items()
                if not any(
                    part in str(key or "").strip().lower()
                    for part in _SENSITIVE_CUSTOM_PARTS
                )
            }
        if isinstance(context, Mapping):
            for key in context.get("preserve_null_fields") or ():
                if key in payload and key not in result:
                    result[str(key)] = None
        return result
    except Exception:
        _logger.warning(
            "field policy evaluation failed",
            extra={"resource_type": str(resource_type or "")},
        )
        return {}


def filter_part_custom_fields(
    user: Any,
    payload: Mapping[str, Any] | None,
    *,
    configured_fields: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Expose configured custom fields only to internal engineering users."""

    if not isinstance(payload, Mapping):
        return {}
    if response_context("parts", user, context=context) != "internal" or not (
        _has(user, "parts.update") or _has(user, "bom.update")
    ):
        return {}
    allowed = {
        str(key or "").strip().lower()
        for key in (configured_fields or {})
        if str(key or "").strip()
    }
    return {
        str(key): deepcopy(value)
        for key, value in payload.items()
        if str(key or "").strip().lower() in allowed
        and not any(
            part in str(key or "").strip().lower()
            for part in _SENSITIVE_CUSTOM_PARTS
        )
    }


def filter_part_field_config(user: Any, config: Mapping[str, Any] | None) -> dict[str, Any]:
    """Remove hidden custom definitions and storage-source configuration."""

    if not isinstance(config, Mapping):
        return {}
    try:
        copied = deepcopy(dict(config))
        engineering = response_context("parts", user) == "internal" and (
            _has(user, "parts.update") or _has(user, "bom.update")
        )
        safe_keys = {
            "id",
            "label",
            "arena_header",
            "kind",
            "data_type",
            "sortable",
            "filterable",
        }
        if engineering:
            safe_keys |= {"source_path", "fallback_paths", "source_locked"}
        fields = []
        for field in copied.get("fields") or []:
            if not isinstance(field, Mapping):
                continue
            field_id = str(field.get("id") or "").strip()
            if not field_id or any(part in field_id.lower() for part in _SENSITIVE_CUSTOM_PARTS):
                continue
            if field.get("kind") == "custom" and not engineering:
                continue
            fields.append({key: deepcopy(value) for key, value in field.items() if key in safe_keys})
        visible_ids = {str(field.get("id") or "") for field in fields}
        contexts: dict[str, Any] = {}
        for name, raw in (copied.get("contexts") or {}).items():
            if not isinstance(raw, Mapping):
                continue
            item = {
                key: [
                    str(field_id)
                    for field_id in raw.get(key) or []
                    if str(field_id) in visible_ids
                ]
                for key in ("required_field_ids", "allowed_field_ids", "default_field_ids")
            }
            item["available_fields"] = [
                deepcopy(field)
                for field in fields
                if field.get("id") in item["allowed_field_ids"]
            ]
            contexts[str(name)] = item
        return {
            "fields": fields,
            "contexts": contexts,
            "canonical_aliases": deepcopy(copied.get("canonical_aliases") or []) if engineering else [],
            "approval_rules": (
                deepcopy(copied.get("approval_rules") or {})
                if engineering
                and (_has(user, "reviews.approve") or _has(user, "parts.release.approve"))
                else {}
            ),
        }
    except Exception:
        _logger.warning("part field-config policy evaluation failed")
        return {}
