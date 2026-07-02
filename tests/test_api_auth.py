from datetime import datetime

from flask import jsonify

from app.models.api_token import ApiToken
from app.models.numbering import NumberingScheme
from app.models.user_settings import UserSettings
from app.services.api_tokens import create_token


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_token_create_and_list(client, user):
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

    token_doc.update(set__revoked_at=datetime.utcnow())
    fail_resp = client.get("/api/auth/check", headers=_auth_headers(raw))
    assert fail_resp.status_code == 401
    assert fail_resp.get_json()["error"] == "invalid_token"


def test_auth_check_requires_token_without_session_fallback(client):
    resp = client.get("/api/auth/check")
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "token_required"


def test_settings_and_numbering_with_bearer(client, user):
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
            {"kind": "field", "field": "type", "casing": "upper"},
            {"kind": "seq", "padding": 3, "base": 10},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 3, "base": 10, "start_at": 1, "reset_policy": "never"},
        revision={"policy": "alpha", "start": "A"},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": datetime.utcnow()},
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
        audit={"created_at": datetime.utcnow()},
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


def test_legacy_aliases_require_auth(client):
    assert client.get("/api/schemes").status_code == 401
    assert client.get("/api/settings").status_code == 401
    assert client.post("/api/preview", json={"scheme_id": "x"}).status_code == 401


def test_legacy_aliases_forward_to_current_handlers(client, user, monkeypatch):
    _, raw = create_token(user, "legacy-aliases")
    headers = _auth_headers(raw)

    import app.views.legacy_addin_api as legacy_addin_api

    monkeypatch.setattr(legacy_addin_api, "list_schemes", lambda: jsonify({"ok": True, "alias": "schemes"}))
    resp = client.get("/api/schemes", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["alias"] == "schemes"

    monkeypatch.setattr(legacy_addin_api, "get_settings", lambda: jsonify({"ok": True, "alias": "settings"}))
    resp = client.get("/api/settings", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["alias"] == "settings"

    monkeypatch.setattr(legacy_addin_api, "preview", lambda: jsonify({"ok": True, "alias": "preview"}))
    resp = client.post("/api/preview", headers=headers, json={"scheme_id": "x"})
    assert resp.status_code == 200
    assert resp.get_json()["alias"] == "preview"
