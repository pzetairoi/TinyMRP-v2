from datetime import timedelta
import uuid

from flask_security.utils import hash_password

from app.models.api_token import ApiToken
from app.models.audit import AuditLog
from app.models.auth import Role, User
from app.services.api_tokens import (
    TokenPolicyError,
    _hash_token,
    create_token,
    token_policy,
    verify_token,
)
from app.services.timezone_utils import utc_now


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = user.get_id()
        session["_fresh"] = True


def _user(app, email, password="Current-password-123", roles=()):
    with app.app_context():
        return User(
            email=email,
            password=hash_password(password),
            active=True,
            fs_uniquifier=str(uuid.uuid4()),
            roles=list(roles),
        ).save()


def test_new_tokens_use_default_expiry_and_enforce_maximum(app, user):
    with app.app_context():
        app.config["API_TOKEN_DEFAULT_TTL_DAYS"] = 30
        app.config["API_TOKEN_MAX_TTL_DAYS"] = 60
        before = utc_now() + timedelta(days=30)
        token, _ = create_token(user, "bounded")
        after = utc_now() + timedelta(days=30)

        assert before <= token.expires_at <= after
        assert token_policy() == {"default_ttl_days": 30, "max_ttl_days": 60}

        try:
            create_token(user, "too-long", lifetime_days=61)
        except TokenPolicyError as exc:
            assert "between 1 and 60 days" in str(exc)
        else:
            raise AssertionError("A token above the configured maximum was created")


def test_invalid_runtime_token_policy_fails_closed(app):
    with app.app_context():
        app.config["API_TOKEN_DEFAULT_TTL_DAYS"] = 91
        app.config["API_TOKEN_MAX_TTL_DAYS"] = 90
        try:
            token_policy()
        except TokenPolicyError as exc:
            assert "cannot exceed" in str(exc)
        else:
            raise AssertionError("An invalid token policy was accepted")


def test_inactive_or_missing_owner_invalidates_token(app, user):
    with app.app_context():
        inactive_doc, inactive_raw = create_token(user, "inactive")
        user.active = False
        user.save()

        assert verify_token(inactive_raw) is None
        inactive_doc.reload()
        assert inactive_doc.revocation_reason == "owner_inactive"

        other = _user(app, "deleted-owner@example.com")
        missing_doc, missing_raw = create_token(other, "missing")
        other.delete()

        assert verify_token(missing_raw) is None
        stored = ApiToken._get_collection().find_one({"_id": missing_doc.id})
        assert stored["revocation_reason"] == "owner_missing"


def test_legacy_token_remains_visible_for_controlled_rotation(client, app, user):
    raw = "tmrp_legacy-token-for-migration"
    with app.app_context():
        legacy = ApiToken(
            user_id=user,
            token_hash=_hash_token(raw),
            label="legacy integration",
        ).save()

    auth = client.get("/api/auth/check", headers=_headers(raw))
    assert auth.status_code == 200

    listing = client.get("/api/me/tokens", headers=_headers(raw)).get_json()
    row = next(item for item in listing["tokens"] if item["id"] == str(legacy.id))
    assert row["status"] == "legacy_no_expiry"
    assert row["legacy_no_expiry"] is True
    assert row["is_active"] is True


def test_user_can_create_rotate_and_revoke_expiring_token(client, app, user):
    bootstrap, bootstrap_raw = create_token(user, "bootstrap")

    created_response = client.post(
        "/api/me/tokens",
        json={"label": "workstation", "expires_in_days": 45},
        headers=_headers(bootstrap_raw),
    )
    assert created_response.status_code == 200
    created = created_response.get_json()
    assert created["token_details"]["status"] == "active"
    assert created["token_details"]["expires_at"]

    too_long = client.post(
        "/api/me/tokens",
        json={"label": "invalid", "expires_in_days": 366},
        headers=_headers(bootstrap_raw),
    )
    assert too_long.status_code == 400
    assert too_long.get_json()["error"]["code"] == "invalid_token_policy"

    rotated_response = client.post(
        f"/api/me/tokens/{created['token_id']}/rotate",
        json={"expires_in_days": 30},
        headers=_headers(bootstrap_raw),
    )
    assert rotated_response.status_code == 200
    rotated = rotated_response.get_json()
    assert rotated["token"] != created["token"]
    assert rotated["replaced_token_id"] == created["token_id"]
    assert client.get("/api/auth/check", headers=_headers(created["token"])).status_code == 401
    assert client.get("/api/auth/check", headers=_headers(rotated["token"])).status_code == 200

    revoked_response = client.delete(
        f"/api/me/tokens/{rotated['token_id']}",
        headers=_headers(bootstrap_raw),
    )
    assert revoked_response.status_code == 200
    assert revoked_response.get_json()["changed"] is True
    assert client.get("/api/auth/check", headers=_headers(rotated["token"])).status_code == 401

    bootstrap.reload()
    assert bootstrap.last_used_at is not None
    rotation_audit = AuditLog.objects(action="api_token.rotate").first()
    assert rotation_audit is not None
    assert rotation_audit.email == user.email
    assert AuditLog.objects(action="api_token.revoke").count() == 1


def test_self_service_password_change_revokes_every_token(client, app):
    user = _user(app, "password-owner@example.com")
    first, first_raw = create_token(user, "first")
    second, second_raw = create_token(user, "second")
    _login(client, user)

    response = client.post(
        "/app/password",
        data={
            "current_password": "Current-password-123",
            "new_password": "Replacement-password-456",
            "confirm_password": "Replacement-password-456",
        },
    )
    assert response.status_code == 302

    first.reload()
    second.reload()
    assert first.revocation_reason == "self_service_password_change"
    assert second.revocation_reason == "self_service_password_change"
    assert verify_token(first_raw) is None
    assert verify_token(second_raw) is None


def test_admin_deactivation_and_password_reset_revoke_tokens(client, app):
    role = Role(
        name="token-lifecycle-admin",
        permissions=["security.users.manage", "security.assignments.manage"],
    ).save()
    actor = _user(app, "lifecycle-admin@example.com", roles=[role])
    deactivated = _user(app, "deactivated@example.com")
    reset_user = _user(app, "reset@example.com")
    deactivated_token, _ = create_token(deactivated, "deactivate")
    reset_token, _ = create_token(reset_user, "reset")
    _login(client, actor)

    deactivation = client.post(
        "/admin/users/bulk-status",
        data={"action": "deactivate", "user_ids": [str(deactivated.id)]},
    )
    assert deactivation.status_code == 302
    deactivated_token.reload()
    assert deactivated_token.revocation_reason == "account_deactivated"

    password_reset = client.post(
        f"/admin/users/{reset_user.id}/edit",
        data={
            "active_present": "1",
            "active": "on",
            "new_password": "Administrator-reset-789",
            "confirm_password": "Administrator-reset-789",
        },
    )
    assert password_reset.status_code == 302
    reset_token.reload()
    assert reset_token.revocation_reason == "administrator_password_reset"


def test_security_admin_can_globally_revoke_tokens(client, app):
    role = Role(
        name="token-revoker",
        permissions=["security.tokens.revoke"],
    ).save()
    actor = _user(app, "token-revoker@example.com", roles=[role])
    target = _user(app, "global-target@example.com")
    actor_token, _ = create_token(actor, "actor integration")
    target_token, _ = create_token(target, "target integration")
    expired = ApiToken(
        user_id=target,
        token_hash="expired-token-hash",
        expires_at=utc_now() - timedelta(days=1),
    ).save()
    _login(client, actor)

    response = client.post("/api/admin/tokens/revoke-all", json={})
    assert response.status_code == 200
    assert response.get_json()["revoked_count"] == 2

    actor_token.reload()
    target_token.reload()
    expired.reload()
    assert actor_token.revocation_reason == "administrator_global_logout"
    assert target_token.revocation_reason == "administrator_global_logout"
    assert expired.revoked_at is None
    audit = AuditLog.objects(action="api_token.admin_revoke_all").first()
    assert audit is not None
    assert audit.extra["revoked_count"] == 2


def test_cli_password_reset_revokes_tokens(app):
    user = _user(app, "cli-reset@example.com")
    token, _ = create_token(user, "cli")

    result = app.test_cli_runner().invoke(
        args=[
            "user",
            "set-password",
            "--email",
            user.email,
            "--password",
            "CLI-replacement-password-456",
        ]
    )
    assert result.exit_code == 0, result.output
    assert "revoked 1 API token(s)" in result.output
    token.reload()
    assert token.revocation_reason == "cli_password_reset"


def test_user_without_permission_cannot_globally_revoke_tokens(client, app):
    actor = _user(app, "ordinary-user@example.com")
    target = _user(app, "still-active@example.com")
    token, raw = create_token(target, "must survive")
    _login(client, actor)

    response = client.post("/api/admin/tokens/revoke-all", json={})
    assert response.status_code == 403
    token.reload()
    assert token.revoked_at is None
    assert verify_token(raw) is not None
