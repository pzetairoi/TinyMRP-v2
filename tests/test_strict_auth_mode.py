from __future__ import annotations

from datetime import timedelta
import uuid

import pytest

import app as app_module
from app.models.auth import Role, User
from app.models.customer import Customer
from app.models.part import Part
from app.services.api_tokens import create_token
from app.services.part_shares import create_part_share
from app.services.security_mode import security_mode
from app.services.timezone_utils import utc_now


STRICT_BASE_URL = "https://localhost"
SAME_ORIGIN = {"Origin": STRICT_BASE_URL}


@pytest.fixture
def strict_app(monkeypatch):
    monkeypatch.setenv("TINYMRP_SECURITY_MODE", "strict")
    monkeypatch.setenv("SECRET_KEY", "s" * 64)
    monkeypatch.setenv("SECURITY_PASSWORD_SALT", "strict-test-password-salt-123456789")
    app_module.init_mongo = lambda _app: None
    application = app_module.create_app()
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return application


@pytest.fixture
def strict_client(strict_app):
    return strict_app.test_client()


def _user(email: str, *, roles=None) -> User:
    return User(
        email=email,
        password="test-password",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=list(roles or []),
    ).save()


def _login(client, user: User) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user.get_id()
        session["_fresh"] = True


def _error_code(response) -> str:
    return response.get_json()["error"]["code"]


def test_security_mode_defaults_to_strict(monkeypatch):
    monkeypatch.delenv("TINYMRP_SECURITY_MODE", raising=False)
    assert security_mode() == "strict"


def test_strict_browser_session_supports_navigation_and_same_origin_api_crud(
    strict_client,
):
    role = Role(name="strict-browser-reader", permissions=["parts.read"]).save()
    user = _user("strict-browser@example.com", roles=[role])
    _login(strict_client, user)

    navigation = strict_client.get("/app", base_url=STRICT_BASE_URL)
    assert navigation.status_code == 200

    summary = strict_client.get("/api/dashboard/summary", base_url=STRICT_BASE_URL)
    assert summary.status_code == 200

    update = strict_client.put(
        "/api/me/settings",
        base_url=STRICT_BASE_URL,
        headers=SAME_ORIGIN,
        json={"ui_preferences": {"show_advanced": True}},
    )
    assert update.status_code == 200
    assert update.get_json()["ok"] is True


def test_strict_session_csrf_rejects_cross_origin_and_missing_origin(strict_client):
    user = _user("strict-csrf@example.com")
    _login(strict_client, user)

    cross_origin = strict_client.put(
        "/api/me/settings",
        base_url=STRICT_BASE_URL,
        headers={"Origin": "https://evil.example"},
        json={"ui_preferences": {"show_advanced": True}},
    )
    assert cross_origin.status_code == 400
    assert _error_code(cross_origin) == "csrf_failed"

    missing_origin = strict_client.put(
        "/api/me/settings",
        base_url=STRICT_BASE_URL,
        json={"ui_preferences": {"show_advanced": True}},
    )
    assert missing_origin.status_code == 400
    assert _error_code(missing_origin) == "csrf_failed"


def test_invalid_bearer_cannot_bypass_session_csrf_in_compat(client, user):
    _login(client, user)
    response = client.put(
        "/api/me/settings",
        headers={
            "Authorization": "Bearer definitely-invalid",
            "Origin": "https://evil.example",
        },
        json={"ui_preferences": {"show_advanced": True}},
    )
    assert response.status_code == 400
    assert _error_code(response) == "csrf_failed"


def test_strict_bearer_only_and_dual_use_endpoint_categories(strict_client):
    user = _user("strict-integration@example.com")
    token_doc, raw_token = create_token(user, "strict integration")
    bearer = {"Authorization": f"Bearer {raw_token}"}

    token_check = strict_client.get(
        "/api/auth/check",
        base_url=STRICT_BASE_URL,
        headers=bearer,
    )
    assert token_check.status_code == 200
    assert token_check.get_json()["user"]["email"] == user.email

    dual_use = strict_client.get(
        "/api/me/settings",
        base_url=STRICT_BASE_URL,
        headers=bearer,
    )
    assert dual_use.status_code == 200

    browser_only = strict_client.get(
        "/api/dashboard/summary",
        base_url=STRICT_BASE_URL,
        headers=bearer,
    )
    assert browser_only.status_code == 401
    assert _error_code(browser_only) == "session_required"

    _login(strict_client, user)
    session_on_token_endpoint = strict_client.get(
        "/api/auth/check",
        base_url=STRICT_BASE_URL,
    )
    assert session_on_token_endpoint.status_code == 401
    assert _error_code(session_on_token_endpoint) == "token_required"

    token_doc.update(set__expires_at=utc_now() - timedelta(seconds=1))
    expired = strict_client.get(
        "/api/auth/check",
        base_url=STRICT_BASE_URL,
        headers=bearer,
    )
    assert expired.status_code == 401
    assert _error_code(expired) == "invalid_token"

    invalid = strict_client.get(
        "/api/auth/check",
        base_url=STRICT_BASE_URL,
        headers={"Authorization": "Bearer invalid"},
    )
    assert invalid.status_code == 401
    assert _error_code(invalid) == "invalid_token"


def test_strict_public_share_is_narrow_and_token_scoped(strict_app):
    with strict_app.app_context():
        part = Part(
            part_number="STRICT-SHARE",
            revision="A",
            description="Strict public share",
        ).save()
        share, raw_token = create_part_share(
            part.part_number,
            part.revision,
            expires_in_days=1,
            allow_unreleased=True,
        )
    public_client = strict_app.test_client()
    share_url = f"/api/share/part/{share.id}/{raw_token}/field-config"

    allowed = public_client.get(share_url, base_url=STRICT_BASE_URL)
    assert allowed.status_code == 200
    assert allowed.get_json()["permissions"] == {"can_admin": False}
    assert "no-store" in allowed.headers.get("Cache-Control", "")

    process_meta = public_client.get(
        f"/api/share/part/{share.id}/{raw_token}/process-meta",
        base_url=STRICT_BASE_URL,
    )
    assert process_meta.status_code == 200
    assert "_alias_index" not in process_meta.get_json()

    invalid = public_client.get(
        f"/api/share/part/{share.id}/{'x' * 43}/field-config",
        base_url=STRICT_BASE_URL,
    )
    assert invalid.status_code == 404

    unrelated = public_client.get("/api/parts_lazy", base_url=STRICT_BASE_URL)
    assert unrelated.status_code == 401
    assert _error_code(unrelated) == "authentication_required"


def test_strict_session_preserves_permission_and_customer_row_scope(strict_client):
    customer_role = Role(
        name="customer",
        permissions=["customers.read"],
    ).save()
    user = _user("strict-portal@example.com", roles=[customer_role])
    linked = Customer(code="STRICT-LINKED", name="Linked", users=[user]).save()
    Customer(code="STRICT-OTHER", name="Other").save()
    _login(strict_client, user)

    response = strict_client.get("/api/customers", base_url=STRICT_BASE_URL)
    assert response.status_code == 200
    assert {row["code"] for row in response.get_json()["items"]} == {linked.code}

    forbidden = strict_client.post(
        "/api/customers",
        base_url=STRICT_BASE_URL,
        headers=SAME_ORIGIN,
        json={"name": "Not allowed"},
    )
    assert forbidden.status_code == 403
    assert _error_code(forbidden) == "forbidden"
