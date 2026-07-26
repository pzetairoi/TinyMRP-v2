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
    LEGACY_PERMISSION_COMPATIBILITY,
    LEGACY_PERMISSION_IDENTIFIERS,
    LEGACY_PERMISSIONS,
    PERMISSION_REGISTRY,
    UnknownPermissionsError,
    expand_legacy_permissions,
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
    },
    "supplier": {
        "parts.read",
        "bom.read",
        "files.read",
        "jobs.read",
        "orders.read",
        "suppliers.read",
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
    assert len(LEGACY_PERMISSION_IDENTIFIERS) == len(set(LEGACY_PERMISSION_IDENTIFIERS))
    assert PERMISSION_REGISTRY == CANONICAL_PERMISSIONS | LEGACY_PERMISSIONS


def test_no_permission_is_both_canonical_and_legacy():
    """The role editor renders the two catalogues separately.

    An identifier in both is posted twice and fails duplicate validation, so
    editing any role holding it becomes impossible.
    """

    assert CANONICAL_PERMISSIONS.isdisjoint(LEGACY_PERMISSIONS)


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
    context_source = inspect.getsource(authorization._build_scope_context)
    for slug in EXPECTED_SCOPED_ROLES:
        assert f'"{slug}"' in context_source, (
            f"standard role {slug!r} must be listed in _build_scope_context's "
            "scoped_roles, otherwise its company links are never loaded"
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


def test_registered_legacy_permissions_remain_storable():
    role = Role(name="legacy", permissions=sorted(LEGACY_PERMISSIONS)).save()

    assert set(role.permissions) == LEGACY_PERMISSIONS


def test_legacy_items_permissions_do_not_gain_destructive_or_approval_authority():
    expanded = expand_legacy_permissions(["items.view", "items.edit"])

    assert {
        "parts.read",
        "bom.read",
        "files.read",
        "comments.read",
        "markups.read",
        "parts.create",
        "parts.update",
        "parts.revise",
        "bom.update",
        "files.add",
        "files.replace",
        "comments.write",
        "markups.write",
        "numbering.allocate",
    } <= expanded
    assert {
        "parts.purge",
        "files.purge",
        "imports.override_approved",
    }.isdisjoint(expanded)


def test_legacy_import_and_order_management_exclude_approval_and_override():
    expanded = expand_legacy_permissions(["import.bom", "orders.manage"])

    assert {
        "imports.preview",
        "imports.execute_low_risk",
        "orders.create",
        "orders.update",
        "orders.submit",
        "orders.fulfil",
    } <= expanded
    assert {
        "imports.override_approved",
        "orders.approve",
    }.isdisjoint(expanded)


def test_legacy_party_management_does_not_imply_financial_authority():
    expanded = expand_legacy_permissions(["customers.manage", "suppliers.manage"])

    assert {"customers.update", "suppliers.update"} <= expanded
    assert {
        "customers.financial.read",
        "customers.financial.update",
        "suppliers.financial.read",
        "suppliers.financial.update",
    }.isdisjoint(expanded)


def test_all_legacy_compatibility_targets_are_canonical():
    assert set(LEGACY_PERMISSION_COMPATIBILITY) <= LEGACY_PERMISSIONS
    assert all(
        implied <= CANONICAL_PERMISSIONS
        for implied in LEGACY_PERMISSION_COMPATIBILITY.values()
    )
