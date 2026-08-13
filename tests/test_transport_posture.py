"""Cookie and CSP transport posture (the plain-HTTP LAN regression).

Two hardening measures assume TLS. Hardcoding them broke every plain-HTTP
deployment without breaking localhost, because loopback is a potentially
trustworthy origin and keeps `Secure` cookies and skips
`upgrade-insecure-requests` anyway. That asymmetry is why the fault reached a
LAN install without any developer machine noticing.

These tests pin both directions: HTTPS deployments must keep every measure they
have today, and a declared plain-HTTP address must produce a session a browser
will actually store.
"""

from __future__ import annotations

import mongomock
import pytest
from mongoengine import connect, disconnect

import app as app_module
from app.services.transport_posture import (
    TransportConfigurationError,
    resolve_transport_posture,
    resolve_trusted_proxy_hops,
)


def _make_app(monkeypatch, **env):
    monkeypatch.setenv("SECRET_KEY", "transport-test-secret-key")
    monkeypatch.setenv("SECURITY_PASSWORD_SALT", "transport-test-password-salt")
    for key in ("TINYMRP_URL", "INSTANCE_URL", "TINYMRP_BROWSER_TLS", "TINYMRP_ALLOWED_ORIGINS"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    disconnect(alias="tinymrp-v2")
    connect(
        alias="tinymrp-v2",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
    )
    app_module.init_mongo = lambda _app: None
    application = app_module.create_app()
    application.config["TESTING"] = True
    return application


def _login_page(application, base_url):
    return application.test_client().get("/login", base_url=base_url)


def _set_cookie(response) -> str:
    for key, value in response.headers:
        if key.lower() == "set-cookie" and value.startswith("session="):
            return value
    return ""


# --------------------------------------------------------------------------
# Resolution logic
# --------------------------------------------------------------------------


def test_https_url_selects_tls_posture():
    posture = resolve_transport_posture({"TINYMRP_URL": "https://tinymrp.example.com"})
    assert posture.browser_tls is True
    assert posture.origin == "https://tinymrp.example.com"
    assert posture.warning is None


def test_plain_http_lan_url_selects_plaintext_posture_and_warns():
    posture = resolve_transport_posture({"TINYMRP_URL": "http://192.168.1.50:5000"})
    assert posture.browser_tls is False
    assert posture.origin == "http://192.168.1.50:5000"
    assert posture.warning and "clear text" in posture.warning


def test_loopback_is_plaintext_without_a_warning():
    """Loopback carries no network exposure, so a warning would be noise."""
    posture = resolve_transport_posture({"TINYMRP_URL": "http://localhost:5000"})
    assert posture.browser_tls is False
    assert posture.warning is None


def test_no_declared_address_still_assumes_tls():
    """Back-compat: every deployment predating TINYMRP_URL got the TLS posture.

    Guessing the other way would silently downgrade a live public instance on
    upgrade, which is a far worse failure than a visibly broken login.
    """
    posture = resolve_transport_posture({})
    assert posture.browser_tls is True
    assert posture.source == "default"


def test_instance_url_is_honoured_for_instances_created_before_tinymrp_url():
    posture = resolve_transport_posture({"INSTANCE_URL": "http://shopfloor.test.local"})
    assert posture.browser_tls is False
    assert posture.source == "INSTANCE_URL"


def test_allowed_origins_is_the_last_resort_hint():
    posture = resolve_transport_posture(
        {"TINYMRP_ALLOWED_ORIGINS": "https://a.example.com,https://b.example.com"}
    )
    assert posture.browser_tls is True
    assert posture.origin == "https://a.example.com"


def test_wildcard_allowed_origins_is_not_treated_as_an_address():
    posture = resolve_transport_posture({"TINYMRP_ALLOWED_ORIGINS": "*"})
    assert posture.origin == ""
    assert posture.browser_tls is True


@pytest.mark.parametrize("override,expected", [("true", True), ("false", False)])
def test_explicit_override_beats_the_declared_url(override, expected):
    posture = resolve_transport_posture(
        {
            "TINYMRP_URL": "http://192.168.1.50:5000" if expected else "https://x.example.com",
            "TINYMRP_BROWSER_TLS": override,
        }
    )
    assert posture.browser_tls is expected
    assert posture.source == "TINYMRP_BROWSER_TLS"


def test_a_url_without_a_scheme_is_rejected_loudly():
    """Guessing the scheme would silently pick a security posture."""
    with pytest.raises(TransportConfigurationError) as excinfo:
        resolve_transport_posture({"TINYMRP_URL": "192.168.1.50:5000"})
    assert "scheme" in str(excinfo.value)


def test_a_malformed_legacy_value_is_ignored_rather_than_fatal():
    """A bad INSTANCE_URL must not stop an instance that boots fine today."""
    posture = resolve_transport_posture({"INSTANCE_URL": "not a url"})
    assert posture.source == "default"
    assert posture.browser_tls is True


def test_port_survives_normalisation():
    """An origin missing its port never matches what the browser sends."""
    posture = resolve_transport_posture({"TINYMRP_URL": "http://tinymrp.lan:8080/"})
    assert posture.origin == "http://tinymrp.lan:8080"


def test_trusted_proxy_hops_defaults_to_one_and_accepts_zero():
    assert resolve_trusted_proxy_hops({}) == 1
    assert resolve_trusted_proxy_hops({"TINYMRP_TRUSTED_PROXY_HOPS": "0"}) == 0
    assert resolve_trusted_proxy_hops({"TINYMRP_TRUSTED_PROXY_HOPS": "2"}) == 2
    with pytest.raises(TransportConfigurationError):
        resolve_trusted_proxy_hops({"TINYMRP_TRUSTED_PROXY_HOPS": "-1"})


# --------------------------------------------------------------------------
# End-to-end response behaviour
# --------------------------------------------------------------------------


def test_lan_http_emits_a_cookie_a_browser_will_store(monkeypatch):
    """`Secure` on a plain-HTTP origin is discarded, so login can never stick."""
    application = _make_app(monkeypatch, TINYMRP_URL="http://192.168.1.50:5000")
    resp = _login_page(application, "http://192.168.1.50:5000")

    cookie = _set_cookie(resp)
    assert cookie, "no session cookie was issued"
    assert "Secure" not in cookie
    assert "HttpOnly" in cookie


def test_lan_http_drops_upgrade_insecure_requests(monkeypatch):
    """Otherwise every subresource is requested over TLS on an HTTP port."""
    application = _make_app(monkeypatch, TINYMRP_URL="http://192.168.1.50:5000")
    csp = _login_page(application, "http://192.168.1.50:5000").headers.get(
        "Content-Security-Policy", ""
    )

    assert csp, "no CSP header emitted"
    assert "upgrade-insecure-requests" not in csp
    # The hardening that does not depend on TLS must survive untouched.
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


def test_https_deployment_keeps_every_tls_measure(monkeypatch):
    application = _make_app(monkeypatch, TINYMRP_URL="https://tinymrp.example.com")
    resp = _login_page(application, "https://tinymrp.example.com")

    assert "Secure" in _set_cookie(resp)
    assert "upgrade-insecure-requests" in resp.headers.get("Content-Security-Policy", "")
    assert resp.headers.get("Strict-Transport-Security", "").startswith("max-age=")


def test_samesite_stays_strict_over_plain_http(monkeypatch):
    """SameSite costs nothing without TLS, so plaintext must not relax it."""
    application = _make_app(monkeypatch, TINYMRP_URL="http://192.168.1.50:5000")
    assert "SameSite=Strict" in _set_cookie(_login_page(application, "http://192.168.1.50:5000"))


def test_declared_url_seeds_the_cors_allowlist(monkeypatch):
    """One address should not have to be configured twice."""
    application = _make_app(monkeypatch, TINYMRP_URL="http://192.168.1.50:5000")
    assert application.config["TINYMRP_ALLOWED_ORIGINS"] == "http://192.168.1.50:5000"


def test_an_explicit_allowlist_still_wins(monkeypatch):
    application = _make_app(
        monkeypatch,
        TINYMRP_URL="http://192.168.1.50:5000",
        TINYMRP_ALLOWED_ORIGINS="http://other.example.com",
    )
    assert application.config["TINYMRP_ALLOWED_ORIGINS"] == "http://other.example.com"


def test_a_real_login_completes_over_plain_http_lan(monkeypatch):
    """The end-to-end symptom, reproduced the way a user hits it.

    With a `Secure` cookie on a plain-HTTP origin the browser stores nothing,
    so the CSRF token minted with the login form is gone by the time the form
    is posted. Flask-WTF then rejects the POST with "The CSRF session token is
    missing" and the user is returned to the login page for ever. Only a full
    GET-form/POST-credentials round trip proves that is fixed.
    """
    import re

    from flask_security import hash_password

    from app.models.auth import User

    base = "http://192.168.1.50:5000"
    application = _make_app(monkeypatch, TINYMRP_URL=base)
    with application.app_context():
        User(
            email="lan-user@example.com",
            password=hash_password("lan-user-password-123"),
            active=True,
            fs_uniquifier="lan-transport-1",
        ).save()

    client = application.test_client()
    form = client.get("/login", base_url=base)
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', form.get_data(as_text=True))
    assert match, "login form did not render a CSRF token"

    posted = client.post(
        "/login",
        base_url=base,
        data={
            "email": "lan-user@example.com",
            "password": "lan-user-password-123",
            "csrf_token": match.group(1),
        },
        headers={"Referer": f"{base}/login"},
    )
    assert posted.status_code != 400, "the CSRF session token did not survive"
    assert posted.status_code == 302, posted.get_data(as_text=True)[:400]

    landing = client.get("/app", base_url=base)
    assert landing.status_code == 200, "the authenticated session was not carried"


def _probe_request_view(application):
    """Report what the app believes about a request, through the WSGI stack.

    test_request_context bypasses app.wsgi_app, so it cannot see ProxyFix at
    all - the middleware is exactly what these two tests are about.
    """
    from flask import jsonify, request

    application.add_url_rule(
        "/__transport_probe",
        "transport_probe",
        lambda: jsonify(remote_addr=request.remote_addr, scheme=request.scheme),
    )
    return application.test_client()


def test_proxy_headers_are_ignored_when_no_proxy_is_trusted(monkeypatch):
    """A directly published port must not believe a client's own X-Forwarded-For."""
    application = _make_app(
        monkeypatch,
        TINYMRP_URL="http://192.168.1.50:5000",
        TINYMRP_TRUSTED_PROXY_HOPS="0",
    )
    resp = _probe_request_view(application).get(
        "/__transport_probe",
        base_url="http://192.168.1.50:5000",
        environ_base={"REMOTE_ADDR": "10.0.0.9"},
        headers={"X-Forwarded-For": "1.2.3.4", "X-Forwarded-Proto": "https"},
    )
    assert resp.get_json() == {"remote_addr": "10.0.0.9", "scheme": "http"}


def test_proxy_headers_are_honoured_by_default(monkeypatch):
    """Guided deployments put Caddy or Nginx in front; that must keep working."""
    application = _make_app(monkeypatch, TINYMRP_URL="https://tinymrp.example.com")
    resp = _probe_request_view(application).get(
        "/__transport_probe",
        base_url="http://tinymrp.example.com",
        environ_base={"REMOTE_ADDR": "172.18.0.2"},
        headers={"X-Forwarded-For": "1.2.3.4", "X-Forwarded-Proto": "https"},
    )
    assert resp.get_json() == {"remote_addr": "1.2.3.4", "scheme": "https"}
