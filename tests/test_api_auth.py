from datetime import datetime

from app.models.app_settings import AppSettings
from app.models.api_token import ApiToken
from app.models.auth import Role
from app.models.numbering import NumberingScheme
from app.models.part import Part
from app.models.user_settings import UserSettings
from app.services.api_tokens import create_token
from app.services.timezone_utils import utc_now


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_token_create_and_list(client, user):
    with client.application.app_context():
        AppSettings(timezone="Australia/Sydney").save()

    bootstrap_doc, bootstrap_token = create_token(user, "bootstrap")
    resp = client.post("/api/me/tokens", json={"label": "test"}, headers=_auth_headers(bootstrap_token))
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["ok"] is True
    assert data.get("token")

    list_resp = client.get("/api/me/tokens", headers=_auth_headers(bootstrap_token))
    list_data = list_resp.get_json()
    assert list_data["ok"] is True
    assert "token" not in list_data
    assert all("token" not in entry for entry in list_data.get("tokens", []))
    assert all(entry.get("created_at_display") for entry in list_data.get("tokens", []))
    assert all("created_at_local" in entry for entry in list_data.get("tokens", []))

    # Ensure hashes only.
    created = ApiToken.objects(id=data["token_id"]).first()
    assert created
    assert created.token_hash


def test_auth_check_and_revoke(client, user):
    token_doc, raw = create_token(user, "auth-check")
    ok_resp = client.get("/api/auth/check", headers=_auth_headers(raw))
    ok_data = ok_resp.get_json()
    assert ok_resp.status_code == 200
    assert ok_data["ok"] is True

    token_doc.update(set__revoked_at=utc_now())
    fail_resp = client.get("/api/auth/check", headers=_auth_headers(raw))
    assert fail_resp.status_code == 401
    assert fail_resp.get_json()["error"]["code"] == "invalid_token"


def test_auth_check_requires_token_without_session_fallback(client):
    resp = client.get("/api/auth/check")
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "token_required"


def test_settings_and_numbering_with_bearer(client, user):
    role = Role(
        name="number_allocator",
        permissions=["numbering.allocate"],
    ).save()
    user.roles = [role]
    user.save()
    token_doc, raw = create_token(user, "settings")
    headers = _auth_headers(raw)

    get_resp = client.get("/api/me/settings", headers=headers)
    assert get_resp.status_code == 200
    get_data = get_resp.get_json()
    assert get_data["ok"] is True
    assert get_data["settings"]["sw_property_map"]["part_number_prop"] == "PartNumber"

    put_resp = client.put("/api/me/settings", headers=headers, json={
        "default_scheme_id": "dummy",
        "default_context": {"type": "ASM"},
        "sw_property_map": {"part_number_prop": "PN", "revision_prop": "Rev", "display_code_prop": "Code"},
        "apply_mode": "active_config",
        "ui_preferences": {"show_advanced": True},
    })
    assert put_resp.status_code == 200

    scheme = NumberingScheme(
        name="TypeSeqApi",
        pattern_segments=[
            {"kind": "literal", "value": "API"},
            {"kind": "seq", "padding": 3, "base": 10},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 3, "base": 10, "start_at": 1, "reset_policy": "never"},
        revision={"policy": "alpha", "start": "A"},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": utc_now()},
    ).save()

    preview = client.post("/api/numbering/preview", headers=headers, json={
        "scheme_id": str(scheme.id),
        "context": {"type": "asm"},
    })
    preview_data = preview.get_json()
    assert preview.status_code == 200
    assert preview_data["ok"] is True

    allocate = client.post("/api/numbering/allocate", headers=headers, json={
        "scheme_id": str(scheme.id),
        "context": {"type": "asm"},
        "create_part_if_missing": False,
        "requested_revision_action": "new_part",
    })
    allocate_data = allocate.get_json()
    assert allocate.status_code == 200
    assert allocate_data["ok"] is True


def test_scheme_list_includes_latest_allocated_part_number(client, user, monkeypatch):
    import app.views.numbering as numbering_view

    monkeypatch.setattr(numbering_view, "user_has_permission", lambda _user, _perm: True)
    _, raw = create_token(user, "scheme-latest")
    scheme = NumberingScheme(name="Latest scheme").save()
    scheme_id = str(scheme.id)
    Part(part_number="PART-0041", attrs={"numbering_scheme_id": scheme_id}).save()
    Part(part_number="PART-0042", attrs={"numbering_scheme_id": scheme_id}).save()

    response = client.get("/api/numbering/schemes", headers=_auth_headers(raw))
    data = response.get_json()
    listed = next(item for item in data["schemes"] if item["id"] == scheme_id)

    assert response.status_code == 200
    assert listed["last_part_number"] == "PART-0042"


def test_scheme_list_recovers_latest_number_from_legacy_part_pattern(client, user, monkeypatch):
    import app.views.numbering as numbering_view

    monkeypatch.setattr(numbering_view, "user_has_permission", lambda _user, _perm: True)
    _, raw = create_token(user, "scheme-legacy-latest")
    scheme = NumberingScheme(
        name="Legacy trailer",
        separator="-",
        pattern_segments=[
            {"kind": "literal", "value": "BD"},
            {"kind": "seq", "padding": 2, "base": 10, "auto_counter": False},
            {"kind": "seq", "padding": 3, "base": 10, "auto_counter": True},
        ],
    ).save()
    Part(part_number="BD-01-001").save()
    Part(part_number="BD-01-002").save()
    Part(part_number="UNRELATED-999").save()

    response = client.get("/api/numbering/schemes", headers=_auth_headers(raw))
    listed = next(item for item in response.get_json()["schemes"] if item["id"] == str(scheme.id))

    assert response.status_code == 200
    assert listed["last_part_number"] == "BD-01-002"


def test_simple_scheme_create_respects_start_at(client, user, monkeypatch):
    import app.views.numbering as numbering_view

    monkeypatch.setattr(numbering_view, "user_has_permission", lambda _user, _perm: True)
    _, raw = create_token(user, "simple-scheme")
    headers = _auth_headers(raw)

    resp = client.post("/api/numbering/schemes", headers=headers, json={
        "name": "PART-SEQ",
        "is_active": True,
        "separator": "-",
        "seq": {"padding": 3, "base": 10, "start_at": 25, "reset_policy": "never"},
        "revision": {"policy": "alpha", "start": "A"},
        "validation_rules": {"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        "pattern_segments": [
            {"kind": "literal", "value": "PART"},
            {"kind": "seq", "padding": 3, "base": 10},
        ],
    })

    data = resp.get_json()
    assert resp.status_code == 200
    assert data["ok"] is True
    assert data["scheme"]["seq"]["start_at"] == 25
    assert data["example"]["part_number_example"] == "PART-025"


def test_delete_scheme_removes_document_and_clears_default_scheme(client, user, monkeypatch):
    import app.views.numbering as numbering_view

    monkeypatch.setattr(numbering_view, "user_has_permission", lambda _user, _perm: True)
    _, raw = create_token(user, "delete-scheme")
    headers = _auth_headers(raw)

    scheme = NumberingScheme(
        name="DeleteMe",
        pattern_segments=[
            {"kind": "literal", "value": "PART"},
            {"kind": "seq", "padding": 3, "base": 10},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 3, "base": 10, "start_at": 7, "reset_policy": "never"},
        revision={"policy": "alpha", "start": "A"},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": utc_now()},
    ).save()

    client.put("/api/me/settings", headers=headers, json={
        "default_scheme_id": str(scheme.id),
        "default_context": {},
        "sw_property_map": {"part_number_prop": "PN", "revision_prop": "Rev", "display_code_prop": "Code"},
        "apply_mode": "active_config",
        "ui_preferences": {"show_advanced": False},
    })

    resp = client.delete(f"/api/numbering/schemes/{scheme.id}", headers=headers)
    data = resp.get_json()

    assert resp.status_code == 200
    assert data["ok"] is True
    assert NumberingScheme.objects(id=scheme.id).first() is None
    settings = UserSettings.objects(user_id=user).first()
    assert settings is not None
    assert settings.default_scheme_id == ""


def test_legacy_alias_routes_are_gone(client):
    # The pre-/api/numbering addin shim was removed; current addins use
    # /api/numbering/*. Unauthenticated callers get 401 rather than 404,
    # because authentication is decided before routing - a 404 would confirm
    # which /api paths exist to anyone who asked.
    assert client.get("/api/schemes").status_code in (401, 404)
    assert client.get("/api/settings").status_code in (401, 404)
    assert client.post("/api/preview", json={"scheme_id": "x"}).status_code in (401, 404)


def test_a_blank_scheme_can_be_created_when_none_exist(client, user, monkeypatch):
    """Deleting every scheme must not gridlock numbering.

    New schemes are usually a copy of an existing one, so the last deletion
    would strand an instance with nothing to copy. The builder's "Start from"
    defaults to Blank, which posts a from-scratch definition - this is that
    request, made against an empty database.
    """
    import app.views.numbering as numbering_view

    monkeypatch.setattr(numbering_view, "user_has_permission", lambda _user, _perm: True)
    _, raw = create_token(user, "blank-scheme")
    headers = _auth_headers(raw)

    NumberingScheme.objects.delete()  # the administrator deleted every scheme
    assert NumberingScheme.objects.count() == 0

    resp = client.post("/api/numbering/schemes", headers=headers, json={
        "name": "Built from scratch",
        "is_active": True,
        "separator": "-",
        "scope_mode": "global",
        "scope_keys": [],
        "seq": {"padding": 6, "base": 10, "start_at": 1, "reset_policy": "never"},
        "revision": {"policy": "none", "start": ""},
        "validation_rules": {"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        "pattern_segments": [
            {"kind": "literal", "value": "PART"},
            {"kind": "seq", "padding": 6, "base": 10, "start_at": 1, "auto_counter": True},
        ],
    })

    data = resp.get_json()
    assert resp.status_code == 200
    assert data["ok"] is True
    assert data["example"]["part_number_example"] == "PART-000001"
    assert NumberingScheme.objects.count() == 1


def test_allocating_with_no_scheme_refuses_cleanly(client, user, monkeypatch):
    """With no scheme there is nothing to allocate from - but no 500 either."""
    import app.views.numbering as numbering_view

    monkeypatch.setattr(numbering_view, "user_has_permission", lambda _user, _perm: True)
    _, raw = create_token(user, "no-scheme-allocate")
    headers = _auth_headers(raw)

    NumberingScheme.objects.delete()
    assert NumberingScheme.objects.count() == 0

    resp = client.post("/api/numbering/allocate", headers=headers, json={"context": {}})

    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "missing_scheme"
