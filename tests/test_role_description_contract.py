"""Every standard role's description is a contract with the operator.

Role descriptions are shown in the admin UI and are what a permission test is
checked against, so a claim that the permission set does not back is a bug in
one or the other. These assertions pin both directions.
"""
import pytest

from app.services.standard_roles import STANDARD_ROLES

# Capabilities each description explicitly promises.
GRANTED = {
    "administrator": (
        "imports.override_approved", "parts.purge", "files.purge",
        "system.maintenance", "exports.run", "security.users.manage",
    ),
    "auditor": (
        "audit.read", "orders.financial.read", "customers.financial.read",
        "parts.read", "comments.read", "markups.read",
    ),
    "commercial": (
        "orders.update", "orders.archive", "orders.financial.read",
        "customers.update", "suppliers.update", "jobs.update",
    ),
    "customer": ("jobs.read", "orders.read", "parts.read"),
    "engineering": (
        "parts.update", "bom.update", "files.add", "shares.create",
        "exports.run", "imports.execute_low_risk", "numbering.allocate",
    ),
    "engineering_manager": (
        "reviews.approve", "comments.moderate", "markups.moderate",
        "imports.override_approved", "numbering.manage",
    ),
    "internal": ("comments.write", "exports.run", "parts.read"),
    "security_administrator": (
        "security.users.manage", "security.roles.manage",
        "security.assignments.manage", "security.tokens.revoke", "audit.read",
    ),
    "supplier": ("orders.read", "jobs.read", "parts.read"),
    "workshop": (
        "jobs.stages.update", "jobs.material.issue", "comments.write",
        "markups.write", "files.read",
    ),
}

# Capabilities each description explicitly disclaims ("no ...", "excludes ...").
DENIED = {
    "auditor": (
        "exports.run", "parts.update", "bom.update", "reviews.approve",
        "parts.purge", "files.purge", "orders.update",
    ),
    "commercial": (
        "parts.update", "bom.update", "parts.purge",
        "customers.portal_users.manage", "suppliers.portal_users.manage",
    ),
    "customer": ("suppliers.read", "orders.financial.read", "parts.update"),
    "engineering": (
        "imports.override_approved", "parts.purge", "files.purge",
        "numbering.manage",
    ),
    "engineering_manager": (
        "parts.purge", "files.purge", "orders.update", "customers.update",
    ),
    "internal": (
        "orders.financial.read", "customers.financial.read",
        "parts.update", "bom.update",
    ),
    "security_administrator": (
        "parts.read", "jobs.read", "orders.read", "system.maintenance",
    ),
    "supplier": ("customers.read", "orders.update", "parts.update"),
    "workshop": ("orders.update", "parts.update", "bom.update"),
}


@pytest.mark.parametrize("role", sorted(GRANTED))
def test_description_promises_are_granted(role):
    held = set(STANDARD_ROLES[role].permissions)
    assert not [p for p in GRANTED[role] if p not in held], (
        f"{role} description promises capabilities its permission set lacks"
    )


@pytest.mark.parametrize("role", sorted(DENIED))
def test_description_disclaimers_are_enforced(role):
    held = set(STANDARD_ROLES[role].permissions)
    assert not [p for p in DENIED[role] if p in held], (
        f"{role} description disclaims capabilities its permission set grants"
    )


def test_only_administrator_may_purge_or_maintain():
    """Purge and system maintenance are administrator-only across every role."""
    for name, definition in STANDARD_ROLES.items():
        held = set(definition.permissions)
        exclusive = held & {"parts.purge", "files.purge", "system.maintenance"}
        assert not exclusive or name == "administrator", (
            f"{name} unexpectedly holds {sorted(exclusive)}"
        )


def test_approved_override_is_limited_to_the_documented_roles():
    holders = {
        name for name, d in STANDARD_ROLES.items()
        if "imports.override_approved" in set(d.permissions)
    }
    assert holders == {"administrator", "engineering_manager"}


def test_every_declared_permission_exists_in_the_registry():
    """A description cannot be verified against a permission that isn't real."""
    from app.services.permissions import CANONICAL_PERMISSIONS

    registry = set(CANONICAL_PERMISSIONS)
    for role, names in list(GRANTED.items()) + list(DENIED.items()):
        unknown = [p for p in names if p not in registry]
        assert not unknown, f"{role} references unregistered permissions {unknown}"
