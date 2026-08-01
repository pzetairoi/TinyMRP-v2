"""Fail-closed response fields for portal and sensitive authenticated data."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
from typing import Any

_logger = logging.getLogger("tinymrp.field_policies")


def _fields(value: str) -> frozenset[str]:
    return frozenset(value.split())


_ALIASES = {
    "part": "parts", "bom": "bom_line", "file": "file_metadata",
    "files": "file_metadata", "job": "jobs", "order": "orders",
    "customer": "customers", "supplier": "suppliers",
}
_PARENT = {
    "parts": "parts", "bom_line": "parts", "file_metadata": "parts",
    "comment": "parts", "profile": "parts", "part_dashboard": "parts",
    "part_insight": "parts", "whereused": "parts", "job_order_summary": "parts",
    "jobs": "jobs", "job_stage": "jobs", "job_bom_line": "jobs",
    "job_bom_admin_line": "jobs", "job_stats": "jobs",
    "orders": "orders", "order_line": "orders", "order_reference": "orders",
    "order_stats": "orders", "order_mutation": "orders",
    "customers": "customers", "customer_order": "customers",
    "customer_stats": "customers", "suppliers": "suppliers",
    "supplier_order": "suppliers", "supplier_stats": "suppliers",
    "address": "customers", "contact": "customers",
}
_READ_PERMISSION = {
    "parts": "parts.read", "jobs": "jobs.read", "orders": "orders.read",
    "customers": "customers.read", "suppliers": "suppliers.read",
}

# ``approved`` is part status, not review metadata: every boundary that may
# read a part may see whether it is approved. The approver's identity and date
# stay out of this set and are released separately.
_PART_BASE = _fields(
    """id key row_key part_number pn revision rev display_code description desc
    status category uom qty total_qty alt_group leaf children level material
    finish mass process processes manufacturer mfr_part thumb_urls thumbnail
    has_pdf has_png has_dxf has_step has_edr has_3mf has_ply has_stl
    has_datasheet datasheet field_values classification processes_normalized
    missing_fields deliverables_present deliverables_missing_recommended
    where_used_count total_qty_used approved"""
)
_PART_EXTERNAL = _PART_BASE - _fields(
    """mass manufacturer mfr_part field_values classification
    processes_normalized missing_fields deliverables_present
    deliverables_missing_recommended where_used_count total_qty_used"""
)
_PART_OPERATOR = _PART_EXTERNAL - {"has_datasheet", "datasheet"}
_PART_INTERNAL_SEARCH = _PART_BASE | _fields(
    """attributes attrs notes comments uploader_profile approver_profile approved
    approved_date approved_by pending_review_count pending_review_severity
    has_pending_reviews whereused other_versions jobs_orders parent_pn parent_rev
    parent_desc parent_thumb_urls child_pn child_rev immediate_pn immediate_rev
    immediate_desc top_pn top_rev top_desc parent_part_number parent_revision
    parent_description source job_number order_number order_kind order_status"""
)
_JOB_EXTERNAL = _fields(
    """job_number title description part_number part_revision qty_ordered
    qty_produced status priority scheduled_start scheduled_start_display
    scheduled_end scheduled_end_display bom"""
)
_JOB_OPERATOR = _JOB_EXTERNAL | _fields(
    "qty_scrapped material_reserved stages order_number"
)
_STAGE_SAFE = _fields(
    """stage_id name sequence status started_at started_at_display completed_at
    completed_at_display"""
)
_STAGE_OPERATIONAL = _fields(
    "assigned_to department estimated_hours actual_hours note"
)
_JOB_BOM_SAFE = _fields("pn part_number rev revision qty")
_ORDER_EXTERNAL = _fields(
    """order_number kind description status job customer_po order_date
    order_date_display requested_delivery requested_delivery_display
    job_required_qty total_ordered_for_job promised_delivery
    promised_delivery_display actual_delivery actual_delivery_display
    shipping_method carrier tracking_number lines"""
)
_ORDER_FINANCIAL = _fields(
    "subtotal tax_amount shipping_cost discount_amount total currency"
)
_ORDER_REVIEW = _fields(
    """approved_by approved_at approved_at_display rejection_reason created_at
    created_at_display updated_at updated_at_display"""
)
_ORDER_LINE_SAFE = _fields(
    """pn part_number rev revision qty uom description qty_shipped qty_received
    requested_delivery requested_delivery_display"""
)
_ORDER_LINE_FINANCIAL = _fields(
    "unit_price discount_pct tax_pct line_total"
)
_CUSTOMER_EXTERNAL = _fields(
    """code name description is_company status primary_contact email website
    phone shipping_addresses default_shipping_label"""
)
_CUSTOMER_FINANCIAL = _fields(
    """customer_type segment billing_address tax_id payment_terms credit_limit
    discount_pct currency sales_rep industry"""
)
_SUPPLIER_EXTERNAL = _fields(
    """code name description status categories primary_contact email phone
    website lead_time_days address"""
)
_SUPPLIER_FINANCIAL = _fields(
    "rating tax_id payment_terms currency min_order_value billing_address"
)
_FILE_SAFE = _fields(
    """name filename display_name category ext_group ext size mtime mtime_iso
    modified_at uploaded_at url urls image_urls preview_url thumbnail_url
    preview_available thumbnail_available revision is_dwg mime content_type
    label kind part_number display_revision recorded_at recorded_at_display
    recorded_at_local"""
)
_ADDRESS_SAFE = _fields(
    "label line1 line2 city state postal country is_default"
)
_CONTACT_SAFE = _fields("name title email phone is_primary")
_PROFILE_SAFE = _fields(
    "display_name label initials avatar_color avatar_shape avatar_url"
)
_COMMENT_SAFE = _fields(
    """id ts ts_display ts_local text status priority resolved_at replies
    reply_count author_display author_profile"""
)
_SENSITIVE_TOKENS = (
    "token", "secret", "password", "credential", "private_key", "api_key",
    "storage", "mount", "path",
)
_INTERNAL_DENIED = _fields(
    """password password_hash token token_hash secret api_key private_key
    storage_path mount_path rel_path path sha256 audit_meta audit_internal"""
)
_AUTOCOMPLETE = {
    "parts": _fields("part_number pn revision rev display_code description desc status"),
    "jobs": _fields("job_number title status part_number part_revision"),
    "orders": _fields("order_number description kind status"),
    "customers": _fields("code name status"),
    "suppliers": _fields("code name status"),
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
    if isinstance(context, Mapping):
        explicit = str(
            context.get("policy_context")
            or context.get("boundary")
            or context.get("audience")
            or ""
        ).strip()
        if explicit in {
            "internal", "customer_portal", "supplier_portal",
            "production_operator",
        }:
            return explicit
    parent = _PARENT.get(_normalise(resource_type))
    permission = _READ_PERMISSION.get(parent or "")
    if not permission:
        return ""
    try:
        from app.services.authorization import permission_scope_modes

        modes = permission_scope_modes(user, permission, resource_type=parent)
    except Exception:
        return ""
    if "global" in modes or modes & {
        "purchase", "sales", "purchasing", "customer_business",
    }:
        return "internal"
    if "customer" in modes:
        return "customer_portal"
    if "supplier" in modes:
        return "supplier_portal"
    return "production_operator" if "assigned" in modes else ""


def _external_fields(normalized: str, boundary: str) -> frozenset[str]:
    parts = _PART_OPERATOR if boundary == "production_operator" else _PART_EXTERNAL
    orders = _ORDER_EXTERNAL
    if boundary == "customer_portal":
        orders |= {"customer"}
    elif boundary == "supplier_portal":
        orders |= {"supplier"}
    policies = {
        "parts": parts, "bom_line": parts, "part_insight": parts,
        "file_metadata": _FILE_SAFE,
        "jobs": _JOB_OPERATOR if boundary == "production_operator" else _JOB_EXTERNAL,
        "job_stage": _STAGE_SAFE | (
            _STAGE_OPERATIONAL if boundary == "production_operator" else frozenset()
        ),
        "job_bom_line": _JOB_BOM_SAFE, "orders": orders,
        "order_line": _ORDER_LINE_SAFE,
        "customers": _CUSTOMER_EXTERNAL if boundary == "customer_portal" else frozenset(),
        "suppliers": _SUPPLIER_EXTERNAL if boundary == "supplier_portal" else frozenset(),
        "address": _ADDRESS_SAFE, "contact": frozenset(),
        "comment": _COMMENT_SAFE if boundary == "production_operator" else frozenset(),
        "profile": _PROFILE_SAFE if boundary == "production_operator" else frozenset(),
        "job_stats": _fields("ok status_counts overdue active"),
        "order_stats": _fields("ok status_counts"),
        "order_mutation": _fields("ok removed"),
        "customer_order": _fields("order_number status order_date"),
        "supplier_order": _fields("order_number status order_date"),
        "customer_stats": _fields("ok orders_count last_order_date"),
        "supplier_stats": _fields("ok on_time_rate avg_lead_days orders_count"),
        "part_dashboard": _fields("counts recent_parts top_hardware"),
    }
    if normalized == "whereused":
        return parts | _fields(
            """parent_pn parent_rev parent_desc parent_thumb_urls child_pn child_rev
            immediate_pn immediate_rev immediate_desc top_pn top_rev top_desc
            parent_part_number parent_revision parent_description qty source
            job_id job_number order_id order_number order_kind order_status"""
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
        if value and not any(token in value.lower() for token in _SENSITIVE_TOKENS)
    )


def allowed_read_fields(
    resource_type: str,
    user: Any,
    *,
    context: Mapping[str, Any] | None = None,
) -> frozenset[str]:
    normalized = _normalise(resource_type)
    boundary = response_context(normalized, user, context=context)
    if not boundary:
        return frozenset()
    fields = (
        _PART_INTERNAL_SEARCH | _configured_fields(user, context)
        if boundary == "internal"
        else _external_fields(normalized, boundary)
    )
    if normalized == "comment" and not _has(user, "comments.read"):
        fields = frozenset()
    if normalized == "profile" and not (
        _has(user, "comments.read")
        or _has(user, "markups.read")
        or _has(user, "markups.write")
    ):
        fields = frozenset()
    if (
        normalized == "file_metadata"
        and isinstance(context, Mapping)
        and context.get("markup_source")
        and (_has(user, "markups.read") or _has(user, "markups.write"))
    ):
        fields |= {"id", "source_file_id", "source_fingerprint"}
    if isinstance(context, Mapping) and context.get("surface") == "autocomplete":
        fields &= _AUTOCOMPLETE.get(normalized, frozenset())
    return fields


@lru_cache(maxsize=4096)
def _key_is_internally_safe(key: Any) -> bool:
    """Both inputs are module constants, so the verdict depends only on the key.

    Every row of a listing carries the same keys, so re-scanning each one
    against every sensitive token was pure repetition.
    """

    return key not in _INTERNAL_DENIED and not any(
        token in str(key).lower() for token in _SENSITIVE_TOKENS
    )


def _internal_fields(
    normalized: str,
    user: Any,
    payload: Mapping[str, Any],
    context: Mapping[str, Any] | None,
) -> set[str]:
    fields = {key for key in payload if _key_is_internally_safe(key)}
    if normalized == "file_metadata":
        fields &= set(_FILE_SAFE)
        if isinstance(context, Mapping) and context.get("markup_source") and (
            _has(user, "markups.read") or _has(user, "markups.write")
        ):
            fields |= {"id", "source_file_id", "source_fingerprint"}
    elif normalized == "profile":
        fields &= set(_PROFILE_SAFE)
    elif normalized == "comment":
        fields &= set(_COMMENT_SAFE) if _has(user, "comments.read") else set()
    elif normalized == "address":
        fields &= set(_ADDRESS_SAFE)
    elif normalized == "contact":
        fields &= set(_CONTACT_SAFE)
    elif normalized in {"parts", "bom_line", "part_insight", "whereused"}:
        fields -= {"internal_cost", "cost", "unit_cost", "margin", "gross_margin"}
        if not _has(user, "comments.read"):
            fields -= {
                "notes", "comments", "pending_review_count",
                "pending_review_severity", "has_pending_reviews",
            }
        if not (_has(user, "markups.read") or _has(user, "markups.write")):
            fields.discard("uploader_profile")
        # Approval status is part data: anyone who may read the part must see
        # whether it is approved, or the badge silently reads "not approved".
        # Who approved it, and when, stays with reviewers and auditors.
        if not (_has(user, "reviews.approve") or _has(user, "audit.read")):
            fields -= {"approver_profile", "approved_date", "approved_by"}
    elif normalized == "jobs":
        if not _has(user, "customers.read"):
            fields -= {"customer", "customer_id"}
        if not _has(user, "suppliers.read"):
            fields.discard("vendor_ids")
        if not _has(user, "jobs.assign"):
            fields.discard("participant_ids")
        if not _has(user, "orders.read"):
            fields.discard("order_number")
    elif normalized in {"orders", "order_line"}:
        if not _has(user, "orders.financial.read"):
            fields -= set(_ORDER_FINANCIAL | _ORDER_LINE_FINANCIAL)
        if normalized == "orders":
            if not _has(user, "customers.read"):
                fields -= {"customer", "customer_id"}
            if not _has(user, "suppliers.read"):
                fields -= {"supplier", "supplier_id"}
            if not _has(user, "jobs.read"):
                fields -= {"job", "job_id"}
            if not (_has(user, "orders.approve") or _has(user, "audit.read")):
                fields -= set(_ORDER_REVIEW)
    elif normalized == "customers" and not _has(user, "customers.financial.read"):
        fields -= set(_CUSTOMER_FINANCIAL)
    elif normalized == "suppliers" and not _has(user, "suppliers.financial.read"):
        fields -= set(_SUPPLIER_FINANCIAL)
    elif normalized in {"order_stats", "order_mutation", "customer_order", "supplier_order"}:
        if not _has(user, "orders.financial.read"):
            fields -= {"revenue_month", "avg_order_value", "total"}
    elif normalized == "customer_stats" and not _has(user, "orders.financial.read"):
        fields.discard("total_revenue")
    return fields


def filter_response_fields(
    resource_type: str,
    user: Any,
    payload: Mapping[str, Any],
    *,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    try:
        normalized = _normalise(resource_type)
        if normalized not in _PARENT:
            return {}
        boundary = response_context(normalized, user, context=context)
        if not boundary:
            return {}
        allowed = (
            _internal_fields(normalized, user, payload, context)
            if boundary == "internal"
            else set(_external_fields(normalized, boundary))
        )
        if normalized == "comment" and not _has(user, "comments.read"):
            allowed.clear()
        if normalized == "profile" and not (
            _has(user, "comments.read")
            or _has(user, "markups.read")
            or _has(user, "markups.write")
        ):
            allowed.clear()
        if (
            normalized == "file_metadata"
            and isinstance(context, Mapping)
            and context.get("markup_source")
            and (_has(user, "markups.read") or _has(user, "markups.write"))
        ):
            allowed |= {"id", "source_file_id", "source_fingerprint"}
        if isinstance(context, Mapping) and context.get("surface") == "autocomplete":
            allowed &= set(_AUTOCOMPLETE.get(normalized, frozenset()))
        result = {key: deepcopy(value) for key, value in payload.items() if key in allowed}
        if isinstance(result.get("field_values"), Mapping):
            result["field_values"] = {
                str(key): deepcopy(value)
                for key, value in result["field_values"].items()
                if not any(token in str(key).lower() for token in _SENSITIVE_TOKENS)
            }
        if isinstance(context, Mapping):
            for key in context.get("preserve_null_fields") or ():
                if key in payload and key not in result:
                    result[str(key)] = None
        return result
    except Exception:
        _logger.warning("field policy evaluation failed", extra={"resource_type": resource_type})
        return {}


def filter_part_custom_fields(
    user: Any,
    payload: Mapping[str, Any] | None,
    *,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or response_context(
        "parts", user, context=context
    ) != "internal" or not (_has(user, "parts.update") or _has(user, "bom.update")):
        return {}
    return {
        str(key): deepcopy(value)
        for key, value in payload.items()
        if not any(token in str(key).lower() for token in _SENSITIVE_TOKENS)
    }


def filter_part_field_config(user: Any, config: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(config, Mapping):
        return {}
    try:
        from app.services.field_config import field_requires_runtime_scan

        engineering = response_context("parts", user) == "internal" and (
            _has(user, "parts.update") or _has(user, "bom.update")
        )
        safe_keys = {
            "id", "label", "arena_header", "kind", "data_type",
            "sortable", "filterable",
        }
        if engineering:
            safe_keys |= {"source_path", "fallback_paths", "source_locked"}
        fields = []
        for raw in config.get("fields") or ():
            if not isinstance(raw, Mapping):
                continue
            field_id = str(raw.get("id") or "").strip()
            if not field_id or any(token in field_id.lower() for token in _SENSITIVE_TOKENS):
                continue
            if raw.get("kind") == "custom" and not engineering:
                continue
            field = {key: deepcopy(value) for key, value in raw.items() if key in safe_keys}
            if field_requires_runtime_scan(field_id, dict(config)):
                field["sortable"] = field["filterable"] = False
            fields.append(field)
        visible = {str(field.get("id") or "") for field in fields}
        contexts = {}
        for name, raw in (config.get("contexts") or {}).items():
            if not isinstance(raw, Mapping):
                continue
            item = {
                key: [str(field_id) for field_id in raw.get(key) or () if str(field_id) in visible]
                for key in ("required_field_ids", "allowed_field_ids", "default_field_ids")
            }
            item["available_fields"] = [
                deepcopy(field) for field in fields
                if field.get("id") in item["allowed_field_ids"]
            ]
            contexts[str(name)] = item
        return {
            "fields": fields,
            "contexts": contexts,
            "canonical_aliases": deepcopy(config.get("canonical_aliases") or []) if engineering else [],
            "approval_rules": (
                deepcopy(config.get("approval_rules") or {})
                if engineering and _has(user, "reviews.approve") else {}
            ),
        }
    except Exception:
        _logger.warning("part field-config policy evaluation failed")
        return {}
