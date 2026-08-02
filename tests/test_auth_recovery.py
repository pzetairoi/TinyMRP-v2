import re

import mongomock
import pytest
from mongoengine import connect, disconnect
from flask_security import hash_password

import app as app_module
from app.models.auth import User


def _make_app(monkeypatch, runtime_path):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("SECURITY_PASSWORD_SALT", raising=False)
    monkeypatch.setenv("TINYMRP_SECURITY_MODE", "compat")
    monkeypatch.setenv("TINYMRP_RUNTIME_SECRETS_PATH", str(runtime_path))

    disconnect(alias="tinymrp-v2")
    connect(
        alias="tinymrp-v2",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
    )
    app_module.init_mongo = lambda _app: None
    app = app_module.create_app()
    app.config["TESTING"] = True
    return app


def _csrf_token(client, path="/login"):
    resp = client.get(path)
    html = resp.get_data(as_text=True)
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    assert match, "CSRF token not found"
    return match.group(1)


def test_login_logout_login_with_runtime_secrets(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime_secrets.json"
    app = _make_app(monkeypatch, runtime_path)

    with app.app_context():
        User(
            email="user@example.com",
            password=hash_password("Password123!"),
            active=True,
            fs_uniquifier="u1",
        ).save()

    client = app.test_client()

    csrf = _csrf_token(client, "/login")
    resp1 = client.post(
        "/login",
        data={"email": "user@example.com", "password": "Password123!", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert resp1.status_code in (302, 303)

    out = client.post("/logout", data={"csrf_token": csrf}, follow_redirects=False)
    assert out.status_code in (302, 303)

    csrf2 = _csrf_token(client, "/login")
    resp2 = client.post(
        "/login",
        data={"email": "user@example.com", "password": "Password123!", "csrf_token": csrf2},
        follow_redirects=False,
    )
    assert resp2.status_code in (302, 303)


def test_runtime_secrets_persisted(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime_secrets.json"
    app1 = _make_app(monkeypatch, runtime_path)
    secret1 = app1.config.get("SECRET_KEY")
    salt1 = app1.config.get("SECURITY_PASSWORD_SALT")
    assert runtime_path.exists()

    app2 = _make_app(monkeypatch, runtime_path)
    assert app2.config.get("SECRET_KEY") == secret1
    assert app2.config.get("SECURITY_PASSWORD_SALT") == salt1


def test_runtime_secrets_create_missing_parent_directory(tmp_path, monkeypatch):
    runtime_path = tmp_path / "missing" / "nested" / "runtime_secrets.json"

    app = _make_app(monkeypatch, runtime_path)

    assert app.config.get("SECRET_KEY")
    assert app.config.get("SECURITY_PASSWORD_SALT")
    assert runtime_path.exists()
