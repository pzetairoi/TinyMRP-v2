import io
import os

import pytest
import mongomock
from mongoengine import connect, disconnect
from werkzeug.exceptions import Forbidden

import app as app_module
from app.models.auth import User, Role
from app.files_proxy import _proxy


def _make_app(monkeypatch, **env):
    for key, val in env.items():
        if val is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, val)
    # Use mongomock and bypass real mongo init
    disconnect(alias="tinymrp-v2")
    connect(alias="tinymrp-v2", host="mongodb://localhost", mongo_client_class=mongomock.MongoClient)
    app_module.init_mongo = lambda _app: None
    app = app_module.create_app()
    app.config["TESTING"] = True
    return app


def _login_session(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(getattr(user, "fs_uniquifier", "")) or str(user.id)
        sess["_fresh"] = True


def test_cors_compat_same_origin(monkeypatch):
    app = _make_app(
        monkeypatch,
        TINYMRP_SECURITY_MODE="compat",
        SECRET_KEY="test-secret-123456",
        SECURITY_PASSWORD_SALT="test-salt-123456",
    )
    client = app.test_client()
    resp = client.get("/", headers={"Origin": "http://localhost"})
    assert resp.headers.get("Access-Control-Allow-Origin") == "http://localhost"
    assert resp.headers.get("Access-Control-Allow-Credentials") == "true"


def test_cors_strict_requires_allowlist(monkeypatch):
    app = _make_app(
        monkeypatch,
        TINYMRP_SECURITY_MODE="strict",
        SECRET_KEY="test-secret-123456",
        SECURITY_PASSWORD_SALT="test-salt-123456",
        TINYMRP_ALLOWED_ORIGINS="",
    )
    client = app.test_client()
    resp = client.get("/", headers={"Origin": "http://example.com"})
    assert "Access-Control-Allow-Origin" not in resp.headers


def test_cors_strict_allowlist_no_creds_by_default(monkeypatch):
    app = _make_app(
        monkeypatch,
        TINYMRP_SECURITY_MODE="strict",
        SECRET_KEY="test-secret-123456",
        SECURITY_PASSWORD_SALT="test-salt-123456",
        TINYMRP_ALLOWED_ORIGINS="http://example.com",
    )
    client = app.test_client()
    resp = client.get("/", headers={"Origin": "http://example.com"})
    assert resp.headers.get("Access-Control-Allow-Origin") == "http://example.com"
    assert "Access-Control-Allow-Credentials" not in resp.headers


def test_strict_api_requires_token_even_with_session(monkeypatch):
    app = _make_app(
        monkeypatch,
        TINYMRP_SECURITY_MODE="strict",
        SECRET_KEY="test-secret-123456",
        SECURITY_PASSWORD_SALT="test-salt-123456",
    )
    user = User(email="strict@example.com", password="x", active=True, fs_uniquifier="u1").save()
    client = app.test_client()
    _login_session(client, user)
    resp = client.get("/api/auth/check")
    assert resp.status_code == 401
    assert resp.get_json().get("error") == "token_required"


def test_session_csrf_blocks_cross_origin(monkeypatch):
    app = _make_app(
        monkeypatch,
        TINYMRP_SECURITY_MODE="compat",
        SECRET_KEY="test-secret-123456",
        SECURITY_PASSWORD_SALT="test-salt-123456",
    )
    user = User(email="csrf@example.com", password="x", active=True, fs_uniquifier="u2").save()
    client = app.test_client()
    _login_session(client, user)
    resp = client.put(
        "/api/me/settings",
        json={"ui_preferences": {"show_advanced": True}},
        headers={"Origin": "http://evil.example"},
    )
    assert resp.status_code == 400
    assert resp.get_json().get("error") == "csrf_failed"


def test_files_proxy_blocks_ip_in_strict(monkeypatch):
    app = _make_app(
        monkeypatch,
        TINYMRP_SECURITY_MODE="strict",
        SECRET_KEY="test-secret-123456",
        SECURITY_PASSWORD_SALT="test-salt-123456",
    )
    app.config["FILES_UPSTREAM_BASE"] = "http://127.0.0.1:8080"
    with app.test_request_context("/deliverables/test.txt"):
        with pytest.raises(Forbidden):
            _proxy("deliverables/test.txt")


def test_files_proxy_no_redirects(monkeypatch):
    app = _make_app(
        monkeypatch,
        TINYMRP_SECURITY_MODE="compat",
        SECRET_KEY="test-secret-123456",
        SECURITY_PASSWORD_SALT="test-salt-123456",
    )
    app.config["FILES_UPSTREAM_BASE"] = "http://example.com"
    called = {}

    class DummyResp:
        status_code = 200
        headers = {"Content-Length": "1", "Content-Type": "text/plain"}

        def iter_content(self, chunk_size=1024):
            yield b"x"

    def fake_get(url, headers=None, stream=None, timeout=None, allow_redirects=None):
        called["allow_redirects"] = allow_redirects
        return DummyResp()

    monkeypatch.setattr("app.files_proxy.requests.get", fake_get)
    with app.test_request_context("/deliverables/test.txt"):
        resp = _proxy("deliverables/test.txt")
        assert resp.status_code == 200
    assert called.get("allow_redirects") is False


def test_upload_pack_size_cap(monkeypatch):
    app = _make_app(
        monkeypatch,
        TINYMRP_SECURITY_MODE="compat",
        SECRET_KEY="test-secret",
        SECURITY_PASSWORD_SALT="test-salt",
    )
    app.config["UPLOAD_PACK_MAX_ZIP_MB"] = 1
    role = Role(name="importer", permissions=["import.bom"]).save()
    user = User(email="uploader@example.com", password="x", active=True, fs_uniquifier="u3", roles=[role]).save()
    client = app.test_client()
    _login_session(client, user)

    payload = io.BytesIO(b"x" * (2 * 1024 * 1024))
    data = {"file": (payload, "test.zip")}
    resp = client.post("/api/upload/pack", data=data, content_type="multipart/form-data", headers={"Origin": "http://localhost"})
    assert resp.status_code == 413
