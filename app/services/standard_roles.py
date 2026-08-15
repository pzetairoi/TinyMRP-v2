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


_ENGINEERING = (
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
    "imports.preview",
    "imports.execute_low_risk",
    # Engineering re-publishes its own work from CAD, so overwriting a part
    # that is still a draft is ordinary work rather than a privileged act.
    # Only an approved part stays protected, behind the override below.
    "imports.execute_approved",
    "comments.read",
    "comments.write",
    "markups.read",
    "markups.write",
    "jobs.read",
    "orders.read",
)

_ENGINEERING_MANAGER = _ENGINEERING + (
    "imports.override_approved",
    "comments.moderate",
    "markups.moderate",
    "reviews.approve",
    "numbering.manage",
    "audit.read",
)


STANDARD_ROLES: dict[str, StandardRoleDefinition] = {
    definition.slug: definition
    for definition in (
        _role(
            "administrator",
            "Administrator",
            "Full application authority: business, security, system, imports including approved override, exports, archive and purge.",
            CANONICAL_PERMISSION_IDENTIFIERS,
        ),
        _role(
            "security_administrator",
            "Security Administrator",
            "Delegated users, roles, assignments, token revocation and audit administration; no business or system-maintenance authority.",
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
            "engineering_manager",
            "Engineering Manager",
            "Owns engineering data with review approval, moderation and approved-data import override authority; no purge or commercial authority.",
            _ENGINEERING_MANAGER,
        ),
        _role(
            "engineering",
            "Engineering",
            "Maintains parts, BOMs, files, shares and exports, allocates part numbers and imports packs including overwriting draft data; no numbering-scheme management, approved-data override or purge.",
            _ENGINEERING,
        ),
        _role(
            "commercial",
            "Commercial (Sales & Procurement)",
            "Runs the full purchase and sales order workflow, customer and supplier records with financials, and job planning; no engineering mutation, portal-user administration or purge.",
            (
                "parts.read",
                "bom.read",
                "files.read",
                "exports.run",
                "numbering.allocate",
                "comments.read",
                "comments.write",
                "markups.read",
                "markups.write",
                "jobs.read",
                "jobs.create",
                "jobs.update",
                "jobs.assign",
                "jobs.bom.update",
                "jobs.cancel",
                "jobs.archive",
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
                "customers.read",
                "customers.update",
                "customers.financial.read",
                "customers.financial.update",
                "customers.archive",
                "suppliers.read",
                "suppliers.update",
                "suppliers.financial.read",
                "suppliers.financial.update",
                "suppliers.archive",
            ),
        ),
        _role(
            "internal",
            "Internal (Other Department)",
            "Reads released internal business data, collaborates through comments and pulls documentation; no financial values, unreleased engineering data or mutations.",
            (
                "parts.read",
                "bom.read",
                "files.read",
                "exports.run",
                "jobs.read",
                "orders.read",
                "customers.read",
                "suppliers.read",
                "comments.read",
                "comments.write",
                "markups.read",
            ),
        ),
        _role(
            "workshop",
            "Workshop",
            "Works shop-wide job stages and material issue with released part documentation, comments and drawing markups; no commercial or engineering authority.",
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
            "customer",
            "Customer",
            "Linked-customer jobs, sales orders and exact released part revisions, with scoped drawing-review collaboration; excludes internal and supplier data.",
            (
                "parts.read",
                "bom.read",
                "files.read",
                "jobs.read",
                "orders.read",
                "customers.read",
                "comments.read",
                "comments.write",
                "markups.read",
                "markups.write",
            ),
        ),
        _role(
            "supplier",
            "Supplier",
            "Linked-supplier purchase orders, related job context and only each PO line's released subtree, with scoped drawing-review collaboration; excludes customer and internal data.",
            (
                "parts.read",
                "bom.read",
                "files.read",
                "jobs.read",
                "orders.read",
                "suppliers.read",
                "comments.read",
                "comments.write",
                "markups.read",
                "markups.write",
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
            if "permissions" in drift_fields:
                from app.services.session_lifecycle import revoke_role_sessions

                revoke_role_sessions(
                    role,
                    reason="standard_role_permissions_restored",
                )
            report["updated"].append(slug)

    return report
