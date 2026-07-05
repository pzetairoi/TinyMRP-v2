import time

import pytest

from app.models.artifact import PartFile
from app.services.files_access import file_token_for, resolve_file_token


def _make_pf():
    return PartFile(
        part_number="PN-TOK",
        revision="A",
        ext_group="pdf",
        ext="pdf",
        rel_path="pdf/PN-TOK_REV_A.pdf",
        path="/srv/deliverables/pdf/PN-TOK_REV_A.pdf",
    ).save()


def test_file_token_roundtrip(app):
    with app.app_context():
        pf = _make_pf()
        token = file_token_for(pf)
        resolved = resolve_file_token(token)
        assert resolved is not None
        assert str(resolved[0].id) == str(pf.id)
        assert resolved[1] == "file"


def test_file_token_expires(app):
    with app.app_context():
        app.config["FILES_TOKEN_TTL_SECONDS"] = 1
        pf = _make_pf()
        token = file_token_for(pf)
        assert resolve_file_token(token) is not None
        time.sleep(2.5)  # itsdangerous ages tokens in whole seconds
        assert resolve_file_token(token) is None


def test_file_token_ttl_zero_never_expires(app):
    with app.app_context():
        app.config["FILES_TOKEN_TTL_SECONDS"] = 0
        pf = _make_pf()
        token = file_token_for(pf)
        assert resolve_file_token(token) is not None


def test_legacy_untimed_token_honored_only_with_flag(app):
    from itsdangerous import URLSafeSerializer

    with app.app_context():
        pf = _make_pf()
        secret = app.config["SECRET_KEY"]
        legacy = URLSafeSerializer(secret, salt="tinymrp.files.v1").dumps(
            {"id": str(pf.id), "kind": "file", "pn": pf.part_number, "rev": pf.revision, "rel": pf.rel_path}
        )
        app.config["FILES_ALLOW_LEGACY_TOKENS"] = True
        assert resolve_file_token(legacy) is not None
        app.config["FILES_ALLOW_LEGACY_TOKENS"] = False
        assert resolve_file_token(legacy) is None


def test_garbage_token_rejected(app):
    with app.app_context():
        assert resolve_file_token("not-a-token") is None


def test_login_rate_limited(app, user):
    client = app.test_client()
    # Default login limit is 10/minute — the 11th attempt must be throttled.
    last = None
    for _ in range(11):
        last = client.post(
            "/login",
            data={"email": user.email, "password": "wrong-password"},
            follow_redirects=False,
        )
    assert last is not None
    assert last.status_code == 429


def test_rate_limit_not_hit_by_normal_use(client, user):
    resp = client.post(
        "/login",
        data={"email": user.email, "password": "wrong-password"},
        follow_redirects=False,
    )
    assert resp.status_code != 429


def test_security_headers_present(client):
    resp = client.get("/login")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert resp.headers.get("X-XSS-Protection") == "0"
    assert resp.headers.get("X-Request-ID")


def test_request_id_honors_inbound_header(client):
    resp = client.get("/api/health", headers={"X-Request-ID": "trace-me-123"})
    assert resp.headers.get("X-Request-ID") == "trace-me-123"


def test_health_reports_version(client):
    data = client.get("/api/health").get_json()
    assert data.get("ok") is True
    assert data.get("server_version")
