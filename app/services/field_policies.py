"""Explicit property-level policies for authenticated JSON responses.

The registry is intentionally small and domain-specific.  It does not infer
visibility from model fields, so adding a database property never makes that
property API-visible automatically.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from flask import g, has_request_context


_logger = logging.getLogger("tinymrp.field_policies")

_RESOURCE_ALIASES = {
    "part": "parts",
    "bom": "bom_line",
    "file": "file_metadata",
    "files": "file_metadata",
    "job": "jobs",
    "order": "orders",
    "customer": "customers",
    "supplier": "suppliers",
}

_PARENT_RESOURCE = {
    "parts": "parts",
    "bom_line": "parts",
    "file_metadata": "parts",
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
    "comment": "parts",
    "profile": "parts",
    "part_dashboard": "parts",
    "part_insight": "parts",
    "whereused": "parts",
    "job_order_summary": "parts",
}

_READ_PERMISSION = {
    "parts": "parts.read",
    "jobs": "jobs.read",
    "orders": "orders.read",
    "customers": "customers.read",
    "suppliers": "suppliers.read",
}

_PART_IDENTIFICATION = frozenset(
    {
        "id",
        "key",
        "row_key",
        "part_number",
        "pn",
        "revision",
        "rev",
        "display_code",
        "description",
        "desc",
        "status",
        "category",
        "uom",
        "qty",
        "total_qty",
        "alt_group",
        "leaf",
        "children",
        "level",
    }
)
_PART_ENGINEERING = frozenset(
    {
        "material",
        "finish",
        "mass",
        "process",
        "processes",
        "manufacturer",
        "mfr_part",
        "field_values",
        "attributes",
        "attrs",
        "thumb_urls",
        "thumbnail",
        "has_pdf",
        "has_png",
        "has_dxf",
        "has_step",
        "has_edr",
        "has_3mf",
        "has_ply",
        "has_stl",
        "has_datasheet",
        "datasheet",
        "classification",
        "processes_normalized",
        "missing_fields",
        "deliverables_present",
        "deliverables_missing_recommended",
        "where_used_count",
        "total_qty_used",
    }
)
_PART_REVIEW_SIGNALS = frozenset(
    {
        "pending_review_count",
        "pending_review_severity",
        "has_pending_reviews",
    }
)
_PART_APPROVAL = frozenset(
    {
        "approver_profile",
        "approved",
        "approved_date",
        "approved_by",
    }
)
_PART_RELATIONSHIPS = frozenset(
    {"whereused", "other_versions", "jobs_orders"}
)
_PART_PORTAL = _PART_IDENTIFICATION | frozenset(
    {
        "material",
        "finish",
        "process",
        "processes",
        "thumb_urls",
        "thumbnail",
        "has_pdf",
        "has_png",
        "has_dxf",
        "has_step",
        "has_3mf",
        "has_ply",
        "has_stl",
        "has_datasheet",
    }
)
_PART_OPERATOR = _PART_IDENTIFICATION | frozenset(
    {
        "material",
        "finish",
        "process",
        "processes",
        "thumb_urls",
        "thumbnail",
        "has_pdf",
        "has_png",
        "has_dxf",
        "has_step",
        "has_3mf",
        "has_ply",
        "has_stl",
    }
)

_JOB_IDENTIFICATION = frozenset(
    {
        "job_number",
        "title",
        "description",
        "part_number",
        "part_revision",
        "qty_ordered",
        "qty_produced",
        "qty_scrapped",
        "status",
        "priority",
        "scheduled_start",
        "scheduled_start_display",
        "scheduled_end",
        "scheduled_end_display",
        "actual_start",
        "actual_start_display",
        "actual_end",
        "actual_end_display",
        "material_reserved",
        "bom",
    }
)
_JOB_PLANNING = frozenset(
    {
        "estimated_hours",
        "actual_hours",
        "stages",
        "created_at",
        "created_at_display",
        "updated_at",
        "updated_at_display",
    }
)
_JOB_PORTAL = _JOB_IDENTIFICATION - {
    "qty_scrapped",
    "actual_start",
    "actual_start_display",
    "actual_end",
    "actual_end_display",
    "material_reserved",
}
_JOB_OPERATOR = _JOB_IDENTIFICATION | frozenset({"stages", "order_number"})

_STAGE_SAFE = frozenset(
    {
        "stage_id",
        "name",
        "sequence",
        "status",
        "started_at",
        "started_at_display",
        "completed_at",
        "completed_at_display",
    }
)
_STAGE_OPERATIONAL = frozenset(
    {"assigned_to", "department", "estimated_hours", "actual_hours", "note"}
)
_JOB_BOM_SAFE = frozenset({"pn", "part_number", "rev", "revision", "qty"})
_JOB_BOM_ADMIN = _JOB_BOM_SAFE | frozenset(
    {
        "line_rev",
        "ordered_qty",
        "remaining_qty",
        "orders",
        "can_manage",
    }
)

_ORDER_IDENTIFICATION = frozenset(
    {
        "order_number",
        "kind",
        "description",
        "status",
        "job",
        "customer_po",
        "order_date",
        "order_date_display",
        "requested_delivery",
        "requested_delivery_display",
        "job_required_qty",
        "total_ordered_for_job",
        "promised_delivery",
        "promised_delivery_display",
        "actual_delivery",
        "actual_delivery_display",
        "shipping_method",
        "carrier",
        "tracking_number",
        "lines",
    }
)
_ORDER_FINANCIAL = frozenset(
    {
        "subtotal",
        "tax_amount",
        "shipping_cost",
        "discount_amount",
        "total",
        "currency",
    }
)
_ORDER_REVIEW = frozenset(
    {
        "approved_by",
        "approved_at",
        "approved_at_display",
        "rejection_reason",
        "created_at",
        "created_at_display",
        "updated_at",
        "updated_at_display",
    }
)
_ORDER_LINE_SAFE = frozenset(
    {
        "pn",
        "part_number",
        "rev",
        "revision",
        "qty",
        "uom",
        "description",
        "qty_shipped",
        "qty_received",
        "requested_delivery",
        "requested_delivery_display",
    }
)
_ORDER_LINE_INTERNAL = frozenset({"note"})
_ORDER_LINE_FINANCIAL = frozenset(
    {"unit_price", "discount_pct", "tax_pct", "line_total"}
)

_CUSTOMER_SAFE = frozenset(
    {
        "code",
        "name",
        "description",
        "is_company",
        "status",
        "tags",
        "primary_contact",
        "email",
        "website",
        "phone",
        "shipping_addresses",
        "default_shipping_label",
        "contacts",
    }
)
_CUSTOMER_PORTAL = frozenset(
    {
        "code",
        "name",
        "description",
        "is_company",
        "status",
        "primary_contact",
        "email",
        "website",
        "phone",
        "shipping_addresses",
        "default_shipping_label",
    }
)
_CUSTOMER_FINANCIAL = frozenset(
    {
        "customer_type",
        "segment",
        "billing_address",
        "tax_id",
        "payment_terms",
        "credit_limit",
        "discount_pct",
        "currency",
        "sales_rep",
        "industry",
    }
)

_SUPPLIER_SAFE = frozenset(
    {
        "code",
        "name",
        "description",
        "status",
        "tags",
        "categories",
        "primary_contact",
        "email",
        "phone",
        "website",
        "lead_time_days",
        "address",
        "contacts",
        "created_at",
    }
)
_SUPPLIER_PORTAL = frozenset(
    {
        "code",
        "name",
        "description",
        "status",
        "categories",
        "primary_contact",
        "email",
        "phone",
        "website",
        "lead_time_days",
        "address",
    }
)
_SUPPLIER_FINANCIAL = frozenset(
    {
        "rating",
        "tax_id",
        "payment_terms",
        "currency",
        "min_order_value",
        "billing_address",
    }
)

_FILE_SAFE = frozenset(
    {
        "name",
        "filename",
        "display_name",
        "category",
        "ext_group",
        "ext",
        "size",
        "mtime",
        "mtime_iso",
        "modified_at",
        "uploaded_at",
        "url",
        "urls",
        "image_urls",
        "preview_url",
        "thumbnail_url",
        "preview_available",
        "thumbnail_available",
        "revision",
        "is_dwg",
        "mime",
        "content_type",
        "label",
        "kind",
        "part_number",
        "display_revision",
        "recorded_at",
        "recorded_at_display",
        "recorded_at_local",
    }
)
_FILE_MARKUP_SOURCE = frozenset(
    {"id", "source_file_id", "source_fingerprint"}
)

_COMMENT_SAFE = frozenset(
    {
        "id",
        "ts",
        "ts_display",
        "ts_local",
        "text",
        "status",
        "priority",
        "resolved_at",
        "replies",
        "reply_count",
        "author_display",
        "author_profile",
    }
)
_PROFILE_SAFE = frozenset(
    {
        "display_name",
        "label",
        "initials",
        "avatar_color",
        "avatar_shape",
        "avatar_url",
    }
)
_ADDRESS_SAFE = frozenset(
    {"label", "line1", "line2", "city", "state", "postal", "country", "is_default"}
)
_CONTACT_SAFE = frozenset({"name", "title", "email", "phone", "is_primary"})

_AUTOCOMPLETE_FIELDS = {
    "parts": frozenset(
        {"part_number", "pn", "revision", "rev", "display_code", "description", "desc", "status"}
    ),
    "jobs": frozenset({"job_number", "title", "status", "part_number", "part_revision"}),
    "orders": frozenset({"order_number", "description", "kind", "status"}),
    "customers": frozenset({"code", "name", "status"}),
    "suppliers": frozenset({"code", "name", "status"}),
}

_WRITE_FIELDS = {
    "parts": (
        frozenset(
            {
                "description",
                "category",
                "uom",
                "manufacturer",
                "mfr_part",
                "status",
                "processes",
                "attrs",
                "notes",
            }
        ),
        ("parts.create", "parts.update"),
    ),
    "jobs": (
        frozenset(
            {
                "job_number",
                "title",
                "description",
                "part_number",
                "part_revision",
                "qty_ordered",
                "qty_produced",
                "qty_scrapped",
                "status",
                "priority",
                "scheduled_start",
                "scheduled_end",
                "actual_start",
                "actual_end",
                "material_reserved",
                "estimated_hours",
                "actual_hours",
                "order_number",
                "customer_id",
                "customer_code",
                "vendor_ids",
                "participant_ids",
                "stages",
                "bom",
            }
        ),
        ("jobs.create", "jobs.update"),
    ),
    "orders": (
        frozenset(
            {
                "order_number",
                "description",
                "kind",
                "status",
                "customer_po",
                "order_date",
                "requested_delivery",
                "promised_delivery",
                "actual_delivery",
                "shipping_cost",
                "discount_amount",
                "currency",
                "shipping_address",
                "shipping_method",
                "carrier",
                "tracking_number",
                "lines",
                "customer_id",
                "customer_code",
                "supplier_id",
                "supplier_code",
                "job_id",
            }
        ),
        ("orders.create", "orders.update"),
    ),
    "customers": (
        frozenset(
            {
                "code",
                "name",
                "description",
                "is_company",
                "status",
                "customer_type",
                "segment",
                "tags",
                "contact",
                "email",
                "website",
                "phone",
                "billing_address",
                "shipping_addresses",
                "default_shipping_label",
                "tax_id",
                "payment_terms",
                "credit_limit",
                "discount_pct",
                "currency",
                "sales_rep",
                "industry",
                "contacts",
            }
        ),
        ("customers.update",),
    ),
    "suppliers": (
        frozenset(
            {
                "code",
                "name",
                "description",
                "status",
                "rating",
                "tags",
                "categories",
                "contact",
                "email",
                "phone",
                "website",
                "tax_id",
                "payment_terms",
                "currency",
                "min_order_value",
                "lead_time_days",
                "address",
                "billing_address",
                "contacts",
                "processes",
            }
        ),
        ("suppliers.update",),
    ),
}

_SENSITIVE_CUSTOM_KEY_PARTS = (
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


def _normalise(resource_type: str) -> str:
    value = str(resource_type or "").strip().lower()
    return _RESOURCE_ALIASES.get(value, value)


def _context_values(context: Mapping[str, Any] | str | None) -> tuple[str, str]:
    if isinstance(context, str):
        if context in {
            "internal",
            "customer_portal",
            "supplier_portal",
            "production_operator",
            "public_share",
        }:
            return context, ""
        return "", context
    if not isinstance(context, Mapping):
        return "", ""
    boundary = str(
        context.get("policy_context")
        or context.get("boundary")
        or context.get("audience")
        or ""
    ).strip()
    surface = str(context.get("surface") or "").strip()
    return boundary, surface


def response_context(
    resource_type: str,
    user: Any,
    *,
    context: Mapping[str, Any] | str | None = None,
) -> str:
    """Resolve the mandatory response boundary from contributing scopes."""

    explicit, _surface = _context_values(context)
    if explicit:
        return explicit
    normalized = _normalise(resource_type)
    parent = _PARENT_RESOURCE.get(normalized)
    if not parent:
        return ""
    permission = _READ_PERMISSION.get(parent)
    if not permission:
        return ""
    try:
        from app.services.authorization import permission_scope_modes

        modes = permission_scope_modes(
            user,
            permission,
            resource_type=parent,
        )
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


def _cache() -> dict[tuple[Any, ...], frozenset[str]] | None:
    if not has_request_context():
        return None
    value = getattr(g, "_tinymrp_field_policy_cache", None)
    if value is None:
        value = {}
        setattr(g, "_tinymrp_field_policy_cache", value)
    return value


def _user_key(user: Any) -> str:
    try:
        return str(getattr(user, "id", "") or f"object:{id(user)}")
    except Exception:
        return f"object:{id(user)}"


def _has(user: Any, permission: str) -> bool:
    try:
        from app.services.authorization import has_permission

        return has_permission(user, permission)
    except Exception:
        return False


def _part_fields(user: Any, boundary: str) -> frozenset[str]:
    if boundary in {"customer_portal", "supplier_portal", "public_share"}:
        return _PART_PORTAL
    if boundary == "production_operator":
        return _PART_OPERATOR
    if boundary != "internal":
        return frozenset()
    fields = _PART_IDENTIFICATION | _PART_ENGINEERING | _PART_RELATIONSHIPS
    if _has(user, "comments.read"):
        fields |= frozenset({"notes", "comments"}) | _PART_REVIEW_SIGNALS
    if _has(user, "markups.read"):
        fields |= frozenset({"uploader_profile"}) | _PART_REVIEW_SIGNALS
    if _has(user, "reviews.approve") or _has(user, "audit.read"):
        fields |= _PART_APPROVAL | _PART_REVIEW_SIGNALS
    return fields


def _job_fields(user: Any, boundary: str) -> frozenset[str]:
    if boundary in {"customer_portal", "supplier_portal"}:
        return _JOB_PORTAL
    if boundary == "production_operator":
        return _JOB_OPERATOR
    if boundary != "internal":
        return frozenset()
    fields = _JOB_IDENTIFICATION
    if any(
        _has(user, permission)
        for permission in ("jobs.update", "jobs.assign", "jobs.stages.update", "audit.read")
    ):
        fields |= _JOB_PLANNING
    if _has(user, "customers.read"):
        fields |= frozenset({"customer"})
    if _has(user, "orders.read"):
        fields |= frozenset({"order_number"})
    return fields


def _order_fields(
    user: Any,
    boundary: str,
    context: Mapping[str, Any] | str | None,
) -> frozenset[str]:
    if boundary not in {
        "internal",
        "customer_portal",
        "supplier_portal",
        "production_operator",
    }:
        return frozenset()
    fields = _ORDER_IDENTIFICATION
    if not _has(user, "jobs.read"):
        fields -= frozenset({"job"})
    kind = ""
    if isinstance(context, Mapping):
        kind = str(context.get("order_kind") or "").strip().lower()
    if boundary == "customer_portal":
        fields |= frozenset({"customer"})
    elif boundary == "supplier_portal":
        fields |= frozenset({"supplier"})
    elif boundary == "production_operator":
        fields -= frozenset({"customer_po", "tracking_number"})
    else:
        if kind == "purchase":
            if _has(user, "suppliers.read"):
                fields |= frozenset({"supplier"})
        elif kind == "sales":
            if _has(user, "customers.read"):
                fields |= frozenset({"customer"})
        else:
            if _has(user, "customers.read"):
                fields |= frozenset({"customer"})
            if _has(user, "suppliers.read"):
                fields |= frozenset({"supplier"})
        if _has(user, "orders.approve") or _has(user, "audit.read"):
            fields |= _ORDER_REVIEW
    if _has(user, "orders.financial.read") and boundary == "internal":
        fields |= _ORDER_FINANCIAL
    return fields


def _customer_fields(user: Any, boundary: str) -> frozenset[str]:
    if boundary == "supplier_portal":
        return frozenset()
    if boundary == "customer_portal":
        return _CUSTOMER_PORTAL
    if boundary != "internal":
        return frozenset()
    fields = _CUSTOMER_SAFE
    if _has(user, "customers.financial.read"):
        fields |= _CUSTOMER_FINANCIAL
    return fields


def _supplier_fields(user: Any, boundary: str) -> frozenset[str]:
    if boundary == "customer_portal":
        return frozenset()
    if boundary == "supplier_portal":
        return _SUPPLIER_PORTAL
    if boundary != "internal":
        return frozenset()
    fields = _SUPPLIER_SAFE
    if _has(user, "suppliers.financial.read"):
        fields |= _SUPPLIER_FINANCIAL
    return fields


def _compute_read_fields(
    normalized: str,
    user: Any,
    boundary: str,
    surface: str,
    context: Mapping[str, Any] | str | None,
) -> frozenset[str]:
    if normalized == "parts":
        fields = _part_fields(user, boundary)
    elif normalized == "bom_line":
        fields = _part_fields(user, boundary)
    elif normalized == "file_metadata":
        fields = _FILE_SAFE
        if (
            boundary == "internal"
            and (_has(user, "markups.read") or _has(user, "markups.write"))
            and isinstance(context, Mapping)
            and bool(context.get("markup_source"))
        ):
            fields |= _FILE_MARKUP_SOURCE
    elif normalized == "jobs":
        fields = _job_fields(user, boundary)
    elif normalized == "job_stage":
        fields = _STAGE_SAFE
        if boundary in {"internal", "production_operator"} and (
            _has(user, "jobs.stages.update") or _has(user, "jobs.update")
        ):
            fields |= _STAGE_OPERATIONAL
    elif normalized == "job_bom_line":
        fields = _JOB_BOM_SAFE
    elif normalized == "job_bom_admin_line":
        fields = _JOB_BOM_SAFE
        if boundary == "internal" and (
            _has(user, "jobs.update") or _has(user, "jobs.bom.update")
        ):
            fields = _JOB_BOM_ADMIN
    elif normalized == "orders":
        fields = _order_fields(user, boundary, context)
    elif normalized == "order_line":
        fields = _ORDER_LINE_SAFE
        if boundary == "internal" and _has(user, "orders.update"):
            fields |= _ORDER_LINE_INTERNAL
        if boundary == "internal" and _has(user, "orders.financial.read"):
            fields |= _ORDER_LINE_FINANCIAL
    elif normalized == "order_reference":
        fields = (
            frozenset({"order_number", "href"})
            if boundary == "internal" and _has(user, "orders.read")
            else frozenset()
        )
    elif normalized == "customers":
        fields = _customer_fields(user, boundary)
    elif normalized == "suppliers":
        fields = _supplier_fields(user, boundary)
    elif normalized == "address":
        fields = _ADDRESS_SAFE if boundary in {"internal", "customer_portal", "supplier_portal"} else frozenset()
    elif normalized == "contact":
        fields = _CONTACT_SAFE if boundary == "internal" else frozenset()
    elif normalized == "comment":
        fields = _COMMENT_SAFE if boundary == "internal" and _has(user, "comments.read") else frozenset()
    elif normalized == "profile":
        fields = _PROFILE_SAFE if boundary == "internal" else frozenset()
    elif normalized == "job_stats":
        fields = frozenset({"ok", "status_counts", "overdue", "active"})
    elif normalized == "order_stats":
        fields = frozenset({"ok", "status_counts"})
        if boundary == "internal" and _has(user, "orders.financial.read"):
            fields |= frozenset({"revenue_month", "avg_order_value"})
    elif normalized == "order_mutation":
        fields = frozenset({"ok", "removed"})
        if boundary == "internal" and _has(user, "orders.financial.read"):
            fields |= frozenset({"total"})
    elif normalized == "customer_order":
        fields = frozenset({"order_number", "status", "order_date"})
        if boundary == "internal" and _has(user, "orders.financial.read"):
            fields |= frozenset({"total"})
    elif normalized == "supplier_order":
        fields = frozenset({"order_number", "status", "order_date"})
        if boundary == "internal" and _has(user, "orders.financial.read"):
            fields |= frozenset({"total"})
    elif normalized == "customer_stats":
        fields = frozenset({"ok", "orders_count", "last_order_date"})
        if boundary == "internal" and _has(user, "orders.financial.read"):
            fields |= frozenset({"total_revenue"})
    elif normalized == "supplier_stats":
        fields = frozenset({"ok", "on_time_rate", "avg_lead_days", "orders_count"})
    elif normalized == "part_dashboard":
        fields = frozenset({"counts", "recent_parts", "top_hardware"})
        if boundary == "internal":
            fields |= frozenset({"top_processes", "data_health"})
            if _has(user, "files.read"):
                fields |= frozenset({"doc_coverage"})
    elif normalized == "part_insight":
        fields = _part_fields(user, boundary)
    elif normalized == "whereused":
        fields = _part_fields(user, boundary) | frozenset(
            {
                "id",
                "parent_pn",
                "parent_rev",
                "parent_desc",
                "parent_thumb_urls",
                "child_pn",
                "child_rev",
                "immediate_pn",
                "immediate_rev",
                "immediate_desc",
                "top_pn",
                "top_rev",
                "top_desc",
                "parent_part_number",
                "parent_revision",
                "parent_description",
                "qty",
            }
        )
        if boundary == "internal":
            fields |= frozenset(
                {
                    "row_key",
                    "source",
                    "job_number",
                    "order_number",
                    "order_kind",
                    "order_status",
                }
            )
    elif normalized == "job_order_summary":
        fields = frozenset(
            {
                "source",
                "job_number",
                "order_number",
                "order_kind",
                "order_status",
                "part_number",
                "revision",
                "qty",
                "status",
            }
        )
    else:
        return frozenset()

    if surface == "autocomplete":
        fields &= _AUTOCOMPLETE_FIELDS.get(normalized, frozenset())
    return frozenset(fields)


def allowed_read_fields(
    resource_type: str,
    user: Any,
    *,
    context: Mapping[str, Any] | str | None = None,
) -> frozenset[str]:
    """Return an immutable explicit allowlist for a resource representation."""

    normalized = _normalise(resource_type)
    if normalized not in _PARENT_RESOURCE:
        return frozenset()
    boundary = response_context(normalized, user, context=context)
    if not boundary:
        return frozenset()
    _explicit, surface = _context_values(context)
    cache = _cache()
    key = (_user_key(user), normalized, boundary, surface, repr(dict(context)) if isinstance(context, Mapping) else str(context or ""))
    if cache is not None and key in cache:
        return cache[key]
    try:
        fields = _compute_read_fields(normalized, user, boundary, surface, context)
        if (
            normalized in {"parts", "bom_line", "whereused"}
            and boundary == "internal"
            and isinstance(context, Mapping)
            and (_has(user, "parts.update") or _has(user, "bom.update"))
        ):
            configured = {
                str(field or "").strip()
                for field in (context.get("configured_fields") or ())
                if str(field or "").strip()
                and not any(
                    sensitive in str(field or "").strip().lower()
                    for sensitive in _SENSITIVE_CUSTOM_KEY_PARTS
                )
            }
            fields |= frozenset(configured)
    except Exception:
        fields = frozenset()
    if cache is not None:
        cache[key] = fields
    return fields


def allowed_write_fields(
    resource_type: str,
    user: Any,
    *,
    context: Mapping[str, Any] | str | None = None,
) -> frozenset[str]:
    """Return explicit writable properties; protected fields are never inferred."""

    normalized = _normalise(resource_type)
    definition = _WRITE_FIELDS.get(normalized)
    if not definition:
        return frozenset()
    fields, permissions = definition
    if not any(_has(user, permission) for permission in permissions):
        return frozenset()
    if response_context(normalized, user, context=context) != "internal":
        return frozenset()
    return fields


def filter_response_fields(
    resource_type: str,
    user: Any,
    payload: Mapping[str, Any],
    *,
    context: Mapping[str, Any] | str | None = None,
) -> dict[str, Any]:
    """Copy and filter one representation; policy errors always fail closed."""

    if not isinstance(payload, Mapping):
        return {}
    try:
        allowed = allowed_read_fields(resource_type, user, context=context)
        if not allowed:
            return {}
        result = {
            key: deepcopy(value)
            for key, value in payload.items()
            if key in allowed
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
    context: Mapping[str, Any] | str | None = None,
) -> dict[str, Any]:
    """Filter raw/custom part properties to configured engineering keys."""

    if not isinstance(payload, Mapping):
        return {}
    boundary = response_context("parts", user, context=context)
    if boundary != "internal" or not (
        _has(user, "parts.update") or _has(user, "bom.update")
    ):
        return {}
    allowed = {
        str(key or "").strip().lower()
        for key in (configured_fields or {})
        if str(key or "").strip()
    }
    out: dict[str, Any] = {}
    for key, value in payload.items():
        normalized = str(key or "").strip().lower()
        if not normalized or normalized not in allowed:
            continue
        if any(part in normalized for part in _SENSITIVE_CUSTOM_KEY_PARTS):
            continue
        out[str(key)] = deepcopy(value)
    return out


def filter_part_field_config(
    user: Any,
    config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return only field definitions the caller may use in part responses."""

    if not isinstance(config, Mapping):
        return {}
    try:
        copied = deepcopy(dict(config))
        custom_ids = {
            str(field.get("id") or "").strip()
            for field in copied.get("fields") or []
            if isinstance(field, Mapping)
            and field.get("kind") == "custom"
            and str(field.get("id") or "").strip()
        }
        visible = allowed_read_fields(
            "parts",
            user,
            context={
                "surface": "detail",
                "configured_fields": custom_ids,
            },
        )
        engineering = response_context("parts", user) == "internal" and (
            _has(user, "parts.update") or _has(user, "bom.update")
        )
        safe_definition_keys = {
            "id",
            "label",
            "arena_header",
            "kind",
            "data_type",
            "sortable",
            "filterable",
        }
        if engineering:
            safe_definition_keys |= {
                "source_path",
                "fallback_paths",
                "source_locked",
            }
        fields = [
            {
                key: deepcopy(value)
                for key, value in field.items()
                if key in safe_definition_keys
            }
            for field in copied.get("fields") or []
            if isinstance(field, Mapping)
            and str(field.get("id") or "") in visible
        ]
        visible_ids = {
            str(field.get("id") or "")
            for field in fields
            if field.get("id")
        }
        contexts: dict[str, Any] = {}
        for name, raw_context in (copied.get("contexts") or {}).items():
            if not isinstance(raw_context, Mapping):
                continue
            context_out: dict[str, Any] = {}
            for key in (
                "required_field_ids",
                "allowed_field_ids",
                "default_field_ids",
            ):
                context_out[key] = [
                    str(field_id)
                    for field_id in raw_context.get(key) or []
                    if str(field_id) in visible_ids
                ]
            context_out["available_fields"] = [
                deepcopy(field)
                for field in fields
                if field.get("id") in context_out["allowed_field_ids"]
            ]
            contexts[str(name)] = context_out
        result: dict[str, Any] = {
            "fields": fields,
            "contexts": contexts,
            "canonical_aliases": (
                deepcopy(copied.get("canonical_aliases") or [])
                if engineering
                else []
            ),
            "approval_rules": (
                deepcopy(copied.get("approval_rules") or {})
                if engineering
                and (
                    _has(user, "reviews.approve")
                    or _has(user, "parts.release.approve")
                )
                else {}
            ),
        }
        return result
    except Exception:
        _logger.warning("part field-config policy evaluation failed")
        return {}
