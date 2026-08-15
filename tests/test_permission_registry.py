import inspect

import pytest
from mongoengine.errors import ValidationError

from app.models.auth import Role
from app.services import authorization
from app.services.permissions import (
    CANONICAL_PERMISSION_GROUPS,
    CANONICAL_PERMISSION_IDENTIFIERS,
    CANONICAL_PERMISSIONS,
    DuplicatePermissionsError,
    PERMISSION_REGISTRY,
    UnknownPermissionsError,
    resolve_permissions,
    validate_permissions,
)
from app.services.standard_roles import STANDARD_ROLES


EXPECTED_CANONICAL_PERMISSIONS = {
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
    "imports.preview",
    "imports.execute_low_risk",
    "imports.execute_approved",
    "imports.override_approved",
    "comments.read",
    "comments.write",
    "comments.moderate",
    "markups.read",
    "markups.write",
    "markups.moderate",
    "reviews.approve",
    "jobs.read",
    "jobs.create",
    "jobs.update",
    "jobs.assign",
    "jobs.bom.update",
    "jobs.stages.update",
    "jobs.material.issue",
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
    "customers.portal_users.manage",
    "customers.archive",
    "suppliers.read",
    "suppliers.update",
    "suppliers.financial.read",
    "suppliers.financial.update",
    "suppliers.portal_users.manage",
    "suppliers.archive",
}

EXPECTED_ENGINEERING_PERMISSIONS = {
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
    # Overwriting a draft is ordinary engineering work; only approved parts
    # stay behind imports.override_approved, which this role does not hold.
    "imports.execute_approved",
    "comments.read",
    "comments.write",
    "markups.read",
    "markups.write",
    "jobs.read",
    "orders.read",
}

EXPECTED_ROLE_PERMISSIONS = {
    "administrator": EXPECTED_CANONICAL_PERMISSIONS,
    "security_administrator": {
        "security.users.read",
        "security.users.manage",
        "security.roles.read",
        "security.roles.manage",
        "security.assignments.manage",
        "security.tokens.revoke",
        "audit.read",
    },
    "engineering_manager": EXPECTED_ENGINEERING_PERMISSIONS
    | {
        "imports.execute_approved",
        "imports.override_approved",
        "comments.moderate",
        "markups.moderate",
        "reviews.approve",
        "numbering.manage",
        "audit.read",
    },
    "engineering": EXPECTED_ENGINEERING_PERMISSIONS,
    "commercial": {
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
    },
    "internal": {
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
    },
    "workshop": {
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
    },
    "customer": {
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
    },
    "supplier": {
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
    },
    "auditor": {
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
    },
}

EXPECTED_ROLE_DISPLAY_NAMES = {
    "administrator": "Administrator",
    "security_administrator": "Security Administrator",
    "engineering_manager": "Engineering Manager",
    "engineering": "Engineering",
    "commercial": "Commercial (Sales & Procurement)",
    "internal": "Internal (Other Department)",
    "workshop": "Workshop",
    "customer": "Customer",
    "supplier": "Supplier",
    "auditor": "Auditor",
}

# Standard roles whose visibility must stay narrowed to linked companies.
EXPECTED_SCOPED_ROLES = {
    "customer": "customer",
    "supplier": "supplier",
}


def test_canonical_registry_is_exact_and_has_no_duplicates():
    flattened = [
        permission
        for group in CANONICAL_PERMISSION_GROUPS.values()
        for permission in group
    ]

    assert CANONICAL_PERMISSIONS == EXPECTED_CANONICAL_PERMISSIONS
    assert len(flattened) == len(set(flattened))
    assert tuple(flattened) == CANONICAL_PERMISSION_IDENTIFIERS
    assert PERMISSION_REGISTRY == CANONICAL_PERMISSIONS


def test_standard_roles_have_exact_permissions():
    assert set(STANDARD_ROLES) == set(EXPECTED_ROLE_PERMISSIONS)
    for slug, expected in EXPECTED_ROLE_PERMISSIONS.items():
        assert set(STANDARD_ROLES[slug].permissions) == expected
        assert STANDARD_ROLES[slug].display_name == EXPECTED_ROLE_DISPLAY_NAMES[slug]
        assert STANDARD_ROLES[slug].description


def test_scoped_standard_roles_are_registered_in_the_scope_map():
    """A scoped role missing from the scope map silently gains global visibility.

    ``_scope_modes`` ends its role dispatch with ``modes.add("global")``, so an
    unrecognised role name widens access instead of failing closed.
    """

    source = inspect.getsource(authorization._scope_modes)
    for slug, mode in EXPECTED_SCOPED_ROLES.items():
        assert f'"{slug}": "{mode}"' in source, (
            f"standard role {slug!r} must map to scope mode {mode!r} in "
            "_scope_modes, otherwise it falls through to global scope"
        )
    for slug in EXPECTED_SCOPED_ROLES:
        assert slug in authorization._SCOPED_ROLE_NAMES, (
            f"standard role {slug!r} must be listed in _SCOPED_ROLE_NAMES, "
            "otherwise its company links are never loaded"
        )


def test_unknown_permissions_are_rejected_by_registry_and_role_model():
    with pytest.raises(UnknownPermissionsError, match="unknown.permission"):
        validate_permissions(["parts.read", "unknown.permission"])

    with pytest.raises(ValidationError, match="unknown.permission"):
        Role(name="invalid", permissions=["unknown.permission"]).save()


def test_duplicate_permissions_are_rejected_by_registry_and_role_model():
    with pytest.raises(DuplicatePermissionsError, match="parts.read"):
        validate_permissions(["parts.read", "parts.read"])

    with pytest.raises(ValidationError, match="parts.read"):
        Role(name="duplicate", permissions=["parts.read", "parts.read"]).save()


def test_a_grant_never_confers_authority_beyond_itself():
    """No permission implies another.

    Everyday engineering, import and party-management grants must never leak
    into destructive, approval or financial authority. Resolution validates
    the stored strings and returns exactly them.
    """

    everyday = [
        "parts.read",
        "parts.create",
        "parts.update",
        "parts.revise",
        "bom.read",
        "bom.update",
        "files.read",
        "files.add",
        "files.replace",
        "comments.read",
        "comments.write",
        "markups.read",
        "markups.write",
        "numbering.allocate",
        "imports.preview",
        "imports.execute_low_risk",
        "orders.read",
        "orders.create",
        "orders.update",
        "orders.submit",
        "orders.fulfil",
        "customers.read",
        "customers.update",
        "suppliers.read",
        "suppliers.update",
    ]

    resolved = resolve_permissions(everyday)

    assert resolved == set(everyday)
    assert {
        "parts.purge",
        "files.purge",
        "imports.override_approved",
        "imports.execute_approved",
        "orders.approve",
        "reviews.approve",
        "customers.financial.read",
        "customers.financial.update",
        "suppliers.financial.read",
        "suppliers.financial.update",
    }.isdisjoint(resolved)


def test_resolution_rejects_unregistered_identifiers():
    """Retired coarse strings are no longer storable or resolvable."""

    with pytest.raises(UnknownPermissionsError):
        resolve_permissions(["items.view"])
