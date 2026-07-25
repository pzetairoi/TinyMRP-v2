"""Canonical and transitional permission definitions.

Endpoint enforcement remains on the legacy permission strings during Stage 1.
The compatibility map is intentionally data-only until the central
authorisation service consumes it in Stage 2.
"""

from __future__ import annotations

from collections.abc import Iterable


CANONICAL_PERMISSION_GROUPS: dict[str, tuple[str, ...]] = {
    "security_and_administration": (
        "security.users.read",
        "security.users.manage",
        "security.roles.read",
        "security.roles.manage",
        "security.assignments.manage",
        "security.tokens.revoke",
        "audit.read",
        "system.config.read",
        "system.config.manage",
        "system.storage.manage",
        "system.rebuild",
        "system.maintenance",
    ),
    "parts_bom_and_files": (
        "parts.read",
        "parts.read_unreleased",
        "parts.create",
        "parts.update",
        "parts.revise",
        "parts.release.approve",
        "parts.archive",
        "parts.restore",
        "parts.purge",
        "bom.read",
        "bom.update",
        "files.read",
        "files.add",
        "files.replace",
        "files.archive",
        "files.restore",
        "files.purge",
        "numbering.allocate",
        "numbering.manage",
        "exports.run",
        "shares.create",
        "shares.revoke",
    ),
    "imports": (
        "imports.preview",
        "imports.execute_low_risk",
        "imports.review_high_risk",
        "imports.approve_high_risk",
        "imports.execute_approved",
        "imports.override_approved",
        "imports.rollback",
    ),
    "comments_markups_and_reviews": (
        "comments.read",
        "comments.write",
        "comments.moderate",
        "markups.read",
        "markups.write",
        "markups.moderate",
        "reviews.approve",
    ),
    "jobs": (
        "jobs.read",
        "jobs.create",
        "jobs.update",
        "jobs.assign",
        "jobs.bom.update",
        "jobs.stages.update",
        "jobs.material.issue",
        "jobs.material.receive",
        "jobs.cancel",
        "jobs.archive",
    ),
    "orders": (
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
    ),
    "customers": (
        "customers.read",
        "customers.update",
        "customers.financial.read",
        "customers.financial.update",
        "customers.portal_users.manage",
        "customers.archive",
    ),
    "suppliers": (
        "suppliers.read",
        "suppliers.update",
        "suppliers.financial.read",
        "suppliers.financial.update",
        "suppliers.portal_users.manage",
        "suppliers.archive",
    ),
}

CANONICAL_PERMISSION_IDENTIFIERS = tuple(
    permission
    for permissions in CANONICAL_PERMISSION_GROUPS.values()
    for permission in permissions
)
if len(CANONICAL_PERMISSION_IDENTIFIERS) != len(set(CANONICAL_PERMISSION_IDENTIFIERS)):
    raise RuntimeError("Canonical permission registry contains duplicate identifiers")
CANONICAL_PERMISSIONS = frozenset(CANONICAL_PERMISSION_IDENTIFIERS)

# Existing permission strings remain valid while endpoint enforcement is
# migrated. They are deliberately not aliases in the canonical registry.
LEGACY_PERMISSION_IDENTIFIERS = (
    "users.manage",
    "roles.manage",
    "settings.manage",
    "items.view",
    "items.edit",
    "bom.view",
    "bom.edit",
    "jobs.view",
    "jobs.manage",
    "suppliers.view",
    "suppliers.manage",
    "customers.view",
    "customers.manage",
    "orders.view",
    "orders.manage",
    "workorders.view",
    "workorders.edit",
    "workorders.close",
    "inventory.issue",
    "inventory.receive",
    "mrp.run",
    "reports.view",
    "numbering.manage",
    "tools.view",
    "import.bom",
)
if len(LEGACY_PERMISSION_IDENTIFIERS) != len(set(LEGACY_PERMISSION_IDENTIFIERS)):
    raise RuntimeError("Legacy permission registry contains duplicate identifiers")
LEGACY_PERMISSIONS = frozenset(LEGACY_PERMISSION_IDENTIFIERS)

PERMISSION_REGISTRY = CANONICAL_PERMISSIONS | LEGACY_PERMISSIONS


# Transitional only. Coarse permissions intentionally do not expand to
# approval, permanent purge, approved-data override, or unrelated financial
# authority. This map is consumed by the central service in Stage 2.
LEGACY_PERMISSION_COMPATIBILITY: dict[str, frozenset[str]] = {
    "users.manage": frozenset(
        {
            "security.users.read",
            "security.users.manage",
            "security.assignments.manage",
        }
    ),
    "roles.manage": frozenset({"security.roles.read", "security.roles.manage"}),
    "settings.manage": frozenset({"system.config.read", "system.config.manage"}),
    "items.view": frozenset(
        {
            "parts.read",
            "bom.read",
            "files.read",
            "comments.read",
            "markups.read",
        }
    ),
    "items.edit": frozenset(
        {
            "parts.create",
            "parts.update",
            "parts.revise",
            "bom.update",
            "files.add",
            "files.replace",
            "comments.write",
            "markups.write",
            "numbering.allocate",
        }
    ),
    "bom.view": frozenset({"bom.read"}),
    "bom.edit": frozenset({"bom.update"}),
    "import.bom": frozenset({"imports.preview", "imports.execute_low_risk"}),
    "jobs.view": frozenset({"jobs.read"}),
    "jobs.manage": frozenset(
        {
            "jobs.read",
            "jobs.create",
            "jobs.update",
            "jobs.assign",
            "jobs.bom.update",
            "jobs.stages.update",
            "jobs.material.issue",
            "jobs.material.receive",
            "jobs.cancel",
            "jobs.archive",
        }
    ),
    "workorders.view": frozenset({"jobs.read"}),
    "workorders.edit": frozenset({"jobs.stages.update"}),
    "workorders.close": frozenset({"jobs.stages.update"}),
    "inventory.issue": frozenset({"jobs.material.issue"}),
    "inventory.receive": frozenset({"jobs.material.receive"}),
    "orders.view": frozenset({"orders.read"}),
    "orders.manage": frozenset(
        {
            "orders.read",
            "orders.create",
            "orders.update",
            "orders.submit",
            "orders.fulfil",
        }
    ),
    "customers.view": frozenset({"customers.read"}),
    "customers.manage": frozenset({"customers.read", "customers.update"}),
    "suppliers.view": frozenset({"suppliers.read"}),
    "suppliers.manage": frozenset({"suppliers.read", "suppliers.update"}),
    "numbering.manage": frozenset({"numbering.allocate", "numbering.manage"}),
}


class PermissionValidationError(ValueError):
    """Base error for invalid stored role permissions."""


class UnknownPermissionsError(PermissionValidationError):
    """Raised when a role contains permission strings outside the registry."""

    def __init__(self, permissions: Iterable[str]):
        self.permissions = tuple(sorted(set(permissions)))
        joined = ", ".join(self.permissions)
        super().__init__(f"Unknown permission(s): {joined}")


class DuplicatePermissionsError(PermissionValidationError):
    """Raised when a role repeats a permission identifier."""

    def __init__(self, permissions: Iterable[str]):
        self.permissions = tuple(sorted(set(permissions)))
        joined = ", ".join(self.permissions)
        super().__init__(f"Duplicate permission(s): {joined}")


def unknown_permissions(permissions: Iterable[object] | None) -> frozenset[str]:
    """Return unregistered values without mutating the supplied collection."""

    values = tuple(permissions or ())
    return frozenset(
        str(permission)
        for permission in values
        if not isinstance(permission, str) or permission not in PERMISSION_REGISTRY
    )


def duplicate_permissions(permissions: Iterable[object] | None) -> frozenset[str]:
    """Return identifiers occurring more than once."""

    seen: set[str] = set()
    duplicates: set[str] = set()
    for permission in tuple(permissions or ()):
        value = str(permission)
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return frozenset(duplicates)


def validate_permissions(permissions: Iterable[str] | None) -> tuple[str, ...]:
    """Validate and return permission strings without changing their order."""

    values = tuple(str(permission) for permission in (permissions or ()))
    unknown = unknown_permissions(values)
    if unknown:
        raise UnknownPermissionsError(unknown)
    duplicates = duplicate_permissions(values)
    if duplicates:
        raise DuplicatePermissionsError(duplicates)
    return values


def expand_legacy_permissions(permissions: Iterable[str] | None) -> frozenset[str]:
    """Return registered permissions plus their transitional implications."""

    values = validate_permissions(permissions)
    expanded = set(values)
    for permission in values:
        expanded.update(LEGACY_PERMISSION_COMPATIBILITY.get(permission, ()))
    return frozenset(expanded)
