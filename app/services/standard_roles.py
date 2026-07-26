"""Canonical definitions and safe reconciliation for standard roles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.permissions import (
    CANONICAL_PERMISSION_IDENTIFIERS,
    duplicate_permissions,
    unknown_permissions,
    validate_permissions,
)


@dataclass(frozen=True)
class StandardRoleDefinition:
    slug: str
    display_name: str
    description: str
    permissions: tuple[str, ...]


def _role(
    slug: str,
    display_name: str,
    description: str,
    permissions: tuple[str, ...],
) -> StandardRoleDefinition:
    validate_permissions(permissions)
    return StandardRoleDefinition(slug, display_name, description, permissions)


STANDARD_ROLES: dict[str, StandardRoleDefinition] = {
    definition.slug: definition
    for definition in (
        _role(
            "administrator",
            "Administrator",
            "Full application administration and business authority; includes purge and sensitive financial operations.",
            CANONICAL_PERMISSION_IDENTIFIERS,
        ),
        _role(
            "security_administrator",
            "Security Administrator",
            "Specialised users, roles, assignments, token revocation and audit administration; no business or system-maintenance authority.",
            (
                "security.users.read",
                "security.users.manage",
                "security.roles.read",
                "security.roles.manage",
                "security.assignments.manage",
                "security.tokens.revoke",
                "audit.read",
            ),
        ),
        _role(
            "system_administrator",
            "System Administrator",
            "Specialised configuration, storage, rebuild and maintenance administration with audit access; no routine business authority.",
            (
                "system.config.read",
                "system.config.manage",
                "system.storage.manage",
                "system.rebuild",
                "system.maintenance",
                "audit.read",
            ),
        ),
        _role(
            "engineering_data_steward",
            "Engineering/Data Steward",
            "Maintains released/unreleased engineering data, BOMs, normal files, numbering, shares and exports; no purge, commercial approval or import override.",
            (
                "parts.read",
                "parts.read_unreleased",
                "parts.create",
                "parts.update",
                "parts.revise",
                "bom.read",
                "bom.update",
                "files.read",
                "files.add",
                "files.replace",
                "numbering.allocate",
                "exports.run",
                "shares.create",
                "shares.revoke",
                "comments.read",
                "comments.write",
                "markups.read",
                "markups.write",
            ),
        ),
        _role(
            "import_operator",
            "Import Operator",
            "Runs low-risk imports; cannot overwrite approved or released records.",
            (
                "parts.read",
                "parts.read_unreleased",
                "bom.read",
                "files.read",
                "imports.preview",
                "imports.execute_low_risk",
            ),
        ),
        _role(
            "import_approver",
            "Import Manager",
            "Runs ordinary imports and authorised approved-data override imports.",
            (
                "parts.read",
                "parts.read_unreleased",
                "bom.read",
                "files.read",
                "imports.preview",
                "imports.execute_low_risk",
                "imports.execute_approved",
                "imports.override_approved",
                "audit.read",
            ),
        ),
        _role(
            "planner",
            "Planner",
            "Plans jobs and non-financial orders, with company planning context and engineering collaboration; can submit but cannot approve orders.",
            (
                "parts.read",
                "bom.read",
                "files.read",
                "comments.read",
                "comments.write",
                "markups.read",
                "markups.write",
                "jobs.read",
                "jobs.create",
                "jobs.update",
                "jobs.assign",
                "jobs.bom.update",
                "orders.read",
                "orders.create",
                "orders.update",
                "orders.submit",
                "customers.read",
                "suppliers.read",
                "numbering.allocate",
                "exports.run",
            ),
        ),
        _role(
            "procurement",
            "Procurement",
            "Manages suppliers, purchase orders, purchasing-related jobs and engineering collaboration; no sales or customer-financial authority.",
            (
                "parts.read",
                "bom.read",
                "files.read",
                "comments.read",
                "comments.write",
                "markups.read",
                "markups.write",
                "jobs.read",
                "suppliers.read",
                "suppliers.update",
                "suppliers.financial.read",
                "suppliers.financial.update",
                "orders.read",
                "orders.create",
                "orders.update",
                "orders.financial.read",
                "orders.financial.update",
                "orders.submit",
                "orders.approve",
                "orders.fulfil",
                "orders.ship",
                "orders.cancel",
                "orders.archive",
                "exports.run",
            ),
        ),
        _role(
            "sales_customer_service",
            "Sales/Customer Service",
            "Manages customers, sales orders, customer-related jobs and engineering collaboration; no purchase or supplier-financial authority.",
            (
                "parts.read",
                "bom.read",
                "files.read",
                "comments.read",
                "comments.write",
                "markups.read",
                "markups.write",
                "jobs.read",
                "customers.read",
                "customers.update",
                "customers.financial.read",
                "customers.financial.update",
                "orders.read",
                "orders.create",
                "orders.update",
                "orders.financial.read",
                "orders.financial.update",
                "orders.submit",
                "orders.approve",
                "orders.fulfil",
                "orders.ship",
                "orders.cancel",
                "orders.archive",
                "exports.run",
            ),
        ),
        _role(
            "production_operator",
            "Production Operator",
            "Works only on assigned jobs, exact related parts, stages, material issue, comments and drawing markups.",
            (
                "parts.read",
                "bom.read",
                "files.read",
                "jobs.read",
                "jobs.stages.update",
                "jobs.material.issue",
                "comments.read",
                "comments.write",
                "markups.read",
                "markups.write",
            ),
        ),
        _role(
            "quality_reviewer",
            "Quality Reviewer",
            "Reviews unreleased engineering data and moderates comments/markups without design, BOM or part-release mutation.",
            (
                "parts.read",
                "parts.read_unreleased",
                "bom.read",
                "files.read",
                "comments.read",
                "comments.write",
                "comments.moderate",
                "markups.read",
                "markups.write",
                "markups.moderate",
                "reviews.approve",
                "audit.read",
            ),
        ),
        _role(
            "internal_viewer",
            "Internal Viewer",
            "Reads released, non-financial internal business data without annotations, exports or mutations.",
            (
                "parts.read",
                "bom.read",
                "files.read",
                "jobs.read",
                "orders.read",
                "customers.read",
                "suppliers.read",
            ),
        ),
        _role(
            "customer_portal",
            "Customer Portal",
            "Read-only linked-customer jobs, sales orders and exact released part revisions; excludes internal and supplier data.",
            (
                "parts.read",
                "bom.read",
                "files.read",
                "jobs.read",
                "orders.read",
                "customers.read",
            ),
        ),
        _role(
            "supplier_portal",
            "Supplier Portal",
            "Read-only linked-supplier purchase orders, related jobs and exact released part revisions; excludes customer and internal data.",
            (
                "parts.read",
                "bom.read",
                "files.read",
                "jobs.read",
                "orders.read",
                "suppliers.read",
            ),
        ),
        _role(
            "auditor",
            "Auditor",
            "Broad read-only audit, configuration, financial, business and unreleased visibility; no export, mutation, approval or purge.",
            (
                "audit.read",
                "system.config.read",
                "security.users.read",
                "security.roles.read",
                "parts.read",
                "parts.read_unreleased",
                "bom.read",
                "jobs.read",
                "orders.read",
                "orders.financial.read",
                "customers.read",
                "customers.financial.read",
                "suppliers.read",
                "suppliers.financial.read",
                "comments.read",
                "markups.read",
            ),
        ),
    )
}

STANDARD_ROLE_SLUGS = tuple(STANDARD_ROLES)


def _drift_fields(role: Any, definition: StandardRoleDefinition) -> list[str]:
    fields: list[str] = []
    if getattr(role, "display_name", None) != definition.display_name:
        fields.append("display_name")
    if getattr(role, "description", None) != definition.description:
        fields.append("description")
    if tuple(getattr(role, "permissions", None) or ()) != definition.permissions:
        fields.append("permissions")
    return fields


def reconcile_standard_roles(*, dry_run: bool = False, apply: bool = False) -> dict[str, Any]:
    """Create missing roles and optionally replace drifted canonical fields.

    The safe default creates only missing roles. ``dry_run`` performs no
    writes. ``apply`` is required before an existing role is overwritten.
    User assignments are never changed.
    """

    if dry_run and apply:
        raise ValueError("dry_run and apply are mutually exclusive")

    from app.models.auth import Role

    report: dict[str, Any] = {
        "mode": "dry-run" if dry_run else ("apply" if apply else "create-missing"),
        "created": [],
        "missing": [],
        "updated": [],
        "drifted": [],
        "unchanged": [],
        "invalid_permissions": [],
        "removed_permissions": [],
    }

    for role in Role.objects.only("name", "permissions"):
        unknown = sorted(unknown_permissions(getattr(role, "permissions", None)))
        duplicates = sorted(duplicate_permissions(getattr(role, "permissions", None)))
        if unknown or duplicates:
            report["invalid_permissions"].append(
                {
                    "slug": str(getattr(role, "name", "") or ""),
                    "unknown": unknown,
                    "duplicates": duplicates,
                }
            )
        if unknown:
            report["removed_permissions"].append(
                {
                    "slug": str(getattr(role, "name", "") or ""),
                    "permissions": unknown,
                }
            )

    for slug, definition in STANDARD_ROLES.items():
        role = Role.objects(name=slug).first()
        if role is None:
            if dry_run:
                report["missing"].append(slug)
                continue
            Role(
                name=definition.slug,
                display_name=definition.display_name,
                description=definition.description,
                permissions=list(definition.permissions),
            ).save()
            report["created"].append(slug)
            continue

        drift_fields = _drift_fields(role, definition)
        if not drift_fields:
            report["unchanged"].append(slug)
            continue

        report["drifted"].append({"slug": slug, "fields": drift_fields})
        if apply:
            role.display_name = definition.display_name
            role.description = definition.description
            role.permissions = list(definition.permissions)
            role.save()
            report["updated"].append(slug)

    return report
