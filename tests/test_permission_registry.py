import pytest
from mongoengine.errors import ValidationError

from app.models.auth import Role
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
    "imports.preview",
    "imports.execute_low_risk",
    "imports.review_high_risk",
    "imports.approve_high_risk",
    "imports.execute_approved",
    "imports.override_approved",
    "imports.rollback",
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
    "jobs.material.receive",
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

EXPECTED_ROLE_PERMISSIONS = {
    "security_administrator": {
        "security.users.read",
        "security.users.manage",
        "security.roles.read",
        "security.roles.manage",
        "security.assignments.manage",
        "security.tokens.revoke",
        "audit.read",
    },
    "system_administrator": {
        "system.config.read",
        "system.config.manage",
        "system.storage.manage",
        "system.rebuild",
        "system.maintenance",
        "audit.read",
    },
    "engineering_data_steward": {
        "parts.read",
        "parts.read_unreleased",
        "parts.create",
        "parts.update",
        "parts.revise",
        "parts.archive",
        "parts.restore",
        "bom.read",
        "bom.update",
        "files.read",
        "files.add",
        "files.replace",
        "files.archive",
        "files.restore",
        "numbering.allocate",
        "exports.run",
        "shares.create",
        "shares.revoke",
        "comments.read",
        "comments.write",
        "markups.read",
        "markups.write",
    },
    "import_operator": {
        "parts.read",
        "parts.read_unreleased",
        "bom.read",
        "files.read",
        "imports.preview",
        "imports.execute_low_risk",
    },
    "import_approver": {
        "parts.read",
        "parts.read_unreleased",
        "bom.read",
        "files.read",
        "imports.preview",
        "imports.review_high_risk",
        "imports.approve_high_risk",
        "imports.execute_approved",
        "imports.override_approved",
        "imports.rollback",
        "audit.read",
    },
    "planner": {
        "parts.read",
        "bom.read",
        "files.read",
        "jobs.read",
        "jobs.create",
        "jobs.update",
        "jobs.assign",
        "jobs.bom.update",
        "orders.read",
        "orders.create",
        "orders.update",
        "orders.submit",
        "numbering.allocate",
    },
    "procurement": {
        "parts.read",
        "bom.read",
        "files.read",
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
    },
    "sales_customer_service": {
        "parts.read",
        "bom.read",
        "files.read",
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
    },
    "production_operator": {
        "parts.read",
        "bom.read",
        "files.read",
        "jobs.read",
        "jobs.stages.update",
        "jobs.material.issue",
        "jobs.material.receive",
        "comments.read",
        "comments.write",
    },
    "quality_reviewer": {
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
        "parts.release.approve",
        "audit.read",
    },
    "internal_viewer": {
        "parts.read",
        "bom.read",
        "files.read",
        "jobs.read",
        "orders.read",
        "customers.read",
        "suppliers.read",
    },
    "customer_portal": {
        "parts.read",
        "bom.read",
        "files.read",
        "jobs.read",
        "orders.read",
        "customers.read",
    },
    "supplier_portal": {
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
    "break_glass_administrator": set(),
}

EXPECTED_ROLE_DISPLAY_NAMES = {
    "security_administrator": "Security Administrator",
    "system_administrator": "System Administrator",
    "engineering_data_steward": "Engineering/Data Steward",
    "import_operator": "Import Operator",
    "import_approver": "Import Approver",
    "planner": "Planner",
    "procurement": "Procurement",
    "sales_customer_service": "Sales/Customer Service",
    "production_operator": "Production Operator",
    "quality_reviewer": "Quality Reviewer",
    "internal_viewer": "Internal Viewer",
    "customer_portal": "Customer Portal",
    "supplier_portal": "Supplier Portal",
    "auditor": "Auditor",
    "break_glass_administrator": "Break-glass Administrator",
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


def test_standard_roles_have_exact_permissions():
    assert set(STANDARD_ROLES) == set(EXPECTED_ROLE_PERMISSIONS)
    for slug, expected in EXPECTED_ROLE_PERMISSIONS.items():
        assert set(STANDARD_ROLES[slug].permissions) == expected
        assert STANDARD_ROLES[slug].display_name == EXPECTED_ROLE_DISPLAY_NAMES[slug]
        assert STANDARD_ROLES[slug].description


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
        "parts.release.approve",
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
        "imports.approve_high_risk",
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
