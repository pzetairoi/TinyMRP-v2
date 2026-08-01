"""Canonical permission definitions.

Every identifier here gates a real endpoint or UI control. The coarse legacy
strings that predated this registry were retired with the demo role system
they served.
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
        "parts.purge",
        "bom.read",
        "bom.update",
        "files.read",
        "files.add",
        "files.replace",
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
        "imports.execute_approved",
        "imports.override_approved",
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

# Every registered permission gates a real endpoint or UI control.
PERMISSION_REGISTRY = CANONICAL_PERMISSIONS


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


def resolve_permissions(permissions: Iterable[str] | None) -> frozenset[str]:
    """Return the validated set of registered permissions.

    Each registered identifier gates one endpoint and never implies another, so
    resolution is validation alone.
    """

    return frozenset(validate_permissions(permissions))
