"""Guards for permission-test impersonation.

Impersonation is a privilege-escalation primitive, so each of these asserts one
condition that must hold for the endpoint to be safe.
"""
import uuid

import pytest

from app.models.auth import Role, User
from app.services import impersonation
from app.services.standard_roles import STANDARD_ROLES


def _role(name):
    existing = Role.objects(name=name).first()
    if existing:
        return existing
    perms = list(STANDARD_ROLES[name].permissions) if name in STANDARD_ROLES else []
    return Role(name=name, permissions=perms).save()


def _user(email, *roles, active=True):
    return User(
        email=email, password="t", active=active,
        fs_uniquifier=str(uuid.uuid4()), roles=list(roles),
    ).save()


@pytest.fixture
def enabled(app):
    app.config["ALLOW_PERMISSION_TEST_DATA"] = True
    app.config["PERMISSION_TEST_DATA_DOMAIN"] = "demo.com"
    return app


def test_disabled_instances_expose_nothing(app):
    """Without ALLOW_PERMISSION_TEST_DATA the feature is inert."""
    app.config["ALLOW_PERMISSION_TEST_DATA"] = False
    with app.test_request_context("/"):
        admin = _user("imp-off@t.test", _role("administrator"))
        assert impersonation.enabled() is False
        assert impersonation.may_impersonate(admin) is False
        assert impersonation.available_targets(admin) == []


def test_only_seeded_permtest_users_are_targets(enabled):
    """Real staff accounts are never impersonatable."""
    with enabled.test_request_context("/"):
        admin = _user("imp-admin@t.test", _role("administrator"))
        target = _user("permtest.engineering@demo.com", _role("engineering"))
        _user("real.staff@demo.com", _role("engineering"))
        _user("permtest.other@wrong-domain.com", _role("engineering"))

        emails = [u.email for u in impersonation.available_targets(admin)]
        assert emails == [target.email]
        assert impersonation.resolve_target(admin, "real.staff@demo.com") is None
        assert impersonation.resolve_target(admin, "permtest.other@wrong-domain.com") is None


def test_administrators_are_never_targets(enabled):
    """A permtest-named admin must not be a route to admin rights."""
    with enabled.test_request_context("/"):
        admin = _user("imp-a2@t.test", _role("administrator"))
        _user("permtest.administrator@demo.com", _role("administrator"))
        _user("permtest.secadmin@demo.com", _role("security_administrator"))

        assert impersonation.available_targets(admin) == []


def test_inactive_targets_are_excluded(enabled):
    with enabled.test_request_context("/"):
        admin = _user("imp-a3@t.test", _role("administrator"))
        _user("permtest.workshop@demo.com", _role("workshop"), active=False)
        assert impersonation.available_targets(admin) == []


def test_actor_without_security_permissions_cannot_impersonate(enabled):
    """Engineering holds neither security.users.manage nor assignments.manage."""
    with enabled.test_request_context("/"):
        engineer = _user("imp-eng@t.test", _role("engineering"))
        _user("permtest.customer@demo.com", _role("customer"))

        assert impersonation.may_impersonate(engineer) is False
        assert impersonation.available_targets(engineer) == []
        assert impersonation.resolve_target(engineer, "permtest.customer@demo.com") is None


def test_impersonated_sessions_cannot_chain(enabled):
    """An already-swapped session must not swap again."""
    with enabled.test_request_context("/"):
        admin = _user("imp-a4@t.test", _role("administrator"))
        _user("permtest.commercial@demo.com", _role("commercial"))
        assert impersonation.may_impersonate(admin) is True

        impersonation.begin(admin)
        assert impersonation.impersonator_id() == str(admin.id)
        # Chaining is refused while a swap is active.
        assert impersonation.may_impersonate(admin) is False
        assert impersonation.available_targets(admin) == []

        assert impersonation.end() == str(admin.id)
        assert impersonation.impersonator_id() == ""


def test_endpoint_refuses_a_non_permtest_target(enabled, client):
    """The posted email is re-validated server-side, not trusted from the UI."""
    with enabled.test_request_context("/"):
        admin = _user("imp-post@t.test", _role("administrator"))
        victim = _user("real.person@demo.com", _role("engineering"))
    with client.session_transaction() as session:
        session["_user_id"] = admin.get_id()
        session["_fresh"] = True

    response = client.post(
        "/admin/roles/permission-test/impersonate",
        data={"email": victim.email},
    )
    assert response.status_code in (302, 401, 403)
    if response.status_code == 302:
        assert "/login" in response.headers.get("Location", "")
