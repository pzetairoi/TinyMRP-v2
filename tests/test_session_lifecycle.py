from __future__ import annotations

import time
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from flask_security.utils import hash_password, verify_password

from app.models.audit import AuditLog
from app.models.auth import Role, User
from app.services.session_lifecycle import revoke_user_sessions
from app.services.standard_roles import STANDARD_ROLES, reconcile_standard_roles
from app.views.admin_audit import ACTION_LABELS, _audit_category


def _make_user(app, email: str, *, roles=(), active: bool = True) -> User:
    with app.app_context():
        password = hash_password("current-password-123")
    return User(
        email=email,
        password=password,
        active=active,
        fs_uniquifier=str(uuid.uuid4()),
        roles=list(roles),
    ).save()


def _login(client, user: User) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user.get_id()
        session["_fresh"] = True


def _assert_signed_out(client) -> None:
    response = client.get("/app")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def _security_actor(app) -> User:
    role = Role(
        name=f"session-admin-{uuid.uuid4().hex}",
        permissions=[
            "security.assignments.manage",
            "security.users.manage",
        ],
    ).save()
    return _make_user(app, f"actor-{uuid.uuid4().hex}@example.com", roles=[role])


def test_active_session_survives_until_server_side_revocation(client, app):
    user = _make_user(app, "active-session@example.com")
    old_identity = user.fs_uniquifier
    _login(client, user)

    assert client.get("/app").status_code == 200
    with app.app_context():
        assert revoke_user_sessions(user, reason="test_security_event") is True

    user.reload()
    assert user.active is True
    assert user.fs_uniquifier != old_identity
    _assert_signed_out(client)

    event = AuditLog.objects(
        action="session.security_event_revoke",
        resource=user.email,
    ).get()
    assert event.extra["reason"] == "test_security_event"
    assert event.extra["mechanism"] == "fs_uniquifier_rotation"


def test_unsaved_user_session_revocation_is_rejected(app):
    user = User(
        email="unsaved-session@example.com",
        password="unused",
        fs_uniquifier=str(uuid.uuid4()),
    )
    with app.app_context(), pytest.raises(ValueError, match="unsaved user"):
        revoke_user_sessions(user, reason="test")


def test_inactive_and_reactivated_user_cannot_reuse_old_session(app):
    actor = _security_actor(app)
    target = _make_user(app, "status-session@example.com")
    actor_client = app.test_client()
    target_client = app.test_client()
    _login(actor_client, actor)
    _login(target_client, target)
    original_identity = target.fs_uniquifier

    response = actor_client.post(
        "/admin/users/bulk-status",
        data={"action": "deactivate", "user_ids": [str(target.id)]},
    )
    assert response.status_code == 302
    target.reload()
    assert target.active is False
    assert target.fs_uniquifier != original_identity
    deactivated_identity = target.fs_uniquifier
    _assert_signed_out(target_client)

    response = actor_client.post(
        "/admin/users/bulk-status",
        data={"action": "activate", "user_ids": [str(target.id)]},
    )
    assert response.status_code == 302
    target.reload()
    assert target.active is True
    assert target.fs_uniquifier != deactivated_identity
    _assert_signed_out(target_client)

    reasons = {
        row.extra.get("reason")
        for row in AuditLog.objects(
            action="session.security_event_revoke",
            resource=target.email,
        )
    }
    assert reasons == {"account_deactivated", "account_reactivated"}


def test_deleted_user_session_fails_closed(client, app):
    user = _make_user(app, "deleted-session@example.com")
    _login(client, user)
    assert client.get("/app").status_code == 200

    user.delete()

    _assert_signed_out(client)


def test_expired_signed_session_cookie_is_rejected(client, app):
    user = _make_user(app, "expired-session@example.com")
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(seconds=30)
    serializer = app.session_interface.get_signing_serializer(app)
    assert serializer is not None
    issued_long_ago = int(time.time()) - 3600
    with patch(
        "itsdangerous.timed.TimestampSigner.get_timestamp",
        return_value=issued_long_ago,
    ):
        cookie = serializer.dumps(
            {
                "_fresh": True,
                "_permanent": True,
                "_user_id": user.get_id(),
            }
        )
    client.set_cookie(app.config.get("SESSION_COOKIE_NAME", "session"), cookie)

    _assert_signed_out(client)


def test_self_password_change_signs_out_every_browser_and_audits(app):
    user = _make_user(app, "self-password-session@example.com")
    first_client = app.test_client()
    second_client = app.test_client()
    _login(first_client, user)
    _login(second_client, user)
    old_identity = user.fs_uniquifier

    response = first_client.post(
        "/app/password",
        data={
            "current_password": "current-password-123",
            "new_password": "new-password-4567",
            "confirm_password": "new-password-4567",
        },
    )
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

    user.reload()
    assert user.fs_uniquifier != old_identity
    with app.app_context():
        assert verify_password("new-password-4567", user.password)
    _assert_signed_out(first_client)
    _assert_signed_out(second_client)

    password_event = AuditLog.objects(
        action="account.password.change",
        resource=user.email,
    ).get()
    assert password_event.extra["revoked_browser_sessions"] is True
    session_event = AuditLog.objects(
        action="session.security_event_revoke",
        resource=user.email,
    ).get()
    assert session_event.extra["reason"] == "self_service_password_change"


def test_administrator_password_reset_revokes_target_sessions(app):
    actor = _security_actor(app)
    target = _make_user(app, "admin-reset-session@example.com")
    actor_client = app.test_client()
    target_client = app.test_client()
    _login(actor_client, actor)
    _login(target_client, target)
    old_identity = target.fs_uniquifier

    response = actor_client.post(
        f"/admin/users/{target.id}/edit",
        data={
            "active_present": "1",
            "active": "on",
            "new_password": "administrator-reset-4567",
            "confirm_password": "administrator-reset-4567",
        },
    )
    assert response.status_code == 302
    target.reload()
    assert target.fs_uniquifier != old_identity
    _assert_signed_out(target_client)

    event = AuditLog.objects(
        action="session.security_event_revoke",
        resource=target.email,
    ).get()
    assert event.extra["reason"] == "administrator_password_reset"


def test_cli_password_and_role_changes_rotate_session_identity(app):
    user = _make_user(app, "cli-session@example.com")
    role = Role(
        name=f"cli-session-role-{uuid.uuid4().hex}",
        permissions=["parts.read"],
    ).save()
    runner = app.test_cli_runner()
    initial_identity = user.fs_uniquifier

    password_result = runner.invoke(
        args=[
            "user",
            "set-password",
            "--email",
            user.email,
            "--password",
            "cli-password-reset-4567",
        ]
    )
    assert password_result.exit_code == 0, password_result.output
    assert "signed out existing browser sessions" in password_result.output
    user.reload()
    assert user.fs_uniquifier != initial_identity
    password_identity = user.fs_uniquifier

    role_result = runner.invoke(
        args=[
            "user",
            "grant-role",
            "--email",
            user.email,
            "--role",
            role.name,
        ]
    )
    assert role_result.exit_code == 0, role_result.output
    user.reload()
    assert user.fs_uniquifier != password_identity

    reasons = {
        row.extra.get("reason")
        for row in AuditLog.objects(
            action="session.security_event_revoke",
            resource=user.email,
        )
    }
    assert reasons == {"cli_password_reset", "cli_role_assignment_changed"}


def test_role_permission_edit_revokes_assigned_user_sessions(app):
    role_admin = Role(
        name=f"role_admin_{uuid.uuid4().hex}",
        permissions=["security.roles.manage"],
    ).save()
    actor = _make_user(
        app,
        f"role-editor-{uuid.uuid4().hex}@example.com",
        roles=[role_admin],
    )
    managed_role = Role(
        name=f"managed_role_{uuid.uuid4().hex}",
        display_name="Managed role",
        permissions=["parts.read"],
    ).save()
    target = _make_user(
        app,
        "role-change-session@example.com",
        roles=[managed_role],
    )
    actor_client = app.test_client()
    target_client = app.test_client()
    _login(actor_client, actor)
    _login(target_client, target)
    old_identity = target.fs_uniquifier

    response = actor_client.post(
        f"/admin/roles/{managed_role.id}/edit",
        data={
            "name": managed_role.name,
            "display_name": "Managed role",
            "description": "Permission reduction",
            "permissions": ["files.read"],
        },
    )
    assert response.status_code == 302
    target.reload()
    assert target.fs_uniquifier != old_identity
    _assert_signed_out(target_client)

    event = AuditLog.objects(
        action="session.security_event_revoke",
        resource=target.email,
    ).get()
    assert event.extra["reason"] == "role_definition_changed"


def test_standard_role_permission_restore_revokes_assigned_sessions(app):
    definition = STANDARD_ROLES["commercial"]
    drifted_role = Role(
        name=definition.slug,
        display_name=definition.display_name,
        description=definition.description,
        permissions=["parts.read"],
    ).save()
    user = _make_user(
        app,
        "standard-role-restore-session@example.com",
        roles=[drifted_role],
    )
    old_identity = user.fs_uniquifier

    with app.app_context():
        report = reconcile_standard_roles(apply=True)

    assert "commercial" in report["updated"]
    user.reload()
    assert user.fs_uniquifier != old_identity
    event = AuditLog.objects(
        action="session.security_event_revoke",
        resource=user.email,
    ).get()
    assert event.extra["reason"] == "standard_role_permissions_restored"


def test_session_revocation_has_friendly_audit_label():
    assert _audit_category("session.security_event_revoke") == (
        "access",
        "Access & admin",
    )
    assert ACTION_LABELS["session.security_event_revoke"] == (
        "Signed out existing browser sessions"
    )
