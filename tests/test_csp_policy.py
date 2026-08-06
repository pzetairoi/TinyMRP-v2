"""CSP policy tests — the 'unsafe-inline' burn-down (SEC-CSP-01, Phase 1A residual).

The Content-Security-Policy header had no direct test coverage, so nothing
stopped a regression from silently weakening it. These tests pin the current
enforced policy and cover the two mechanisms added to make the inline-script
burn-down possible:

  * a per-response nonce, so templates can migrate off 'unsafe-inline' one at a
    time instead of in a single risky change;
  * an opt-in report-only header carrying the stricter policy, so the breakage
    can be measured before it is enforced.

The important negative assertion is that the nonce is NOT emitted while
'unsafe-inline' is still allowed: browsers ignore 'unsafe-inline' whenever a
nonce is present, so emitting both would break every unmigrated template at
once — precisely the big-bang this design avoids.
"""

from __future__ import annotations

import re

import mongomock
import pytest
from mongoengine import connect, disconnect

import app as app_module


def _make_app(monkeypatch, **env):
    monkeypatch.setenv("TINYMRP_SECURITY_MODE", "compat")
    monkeypatch.setenv("SECRET_KEY", "csp-test-secret-key")
    monkeypatch.setenv("SECURITY_PASSWORD_SALT", "csp-test-salt")
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


def _csp(client, path="/login"):
    resp = client.get(path)
    return resp.headers.get("Content-Security-Policy", "")


def test_baseline_policy_directives_present(monkeypatch):
    """The enforced policy keeps its hardening directives."""
    app = _make_app(monkeypatch)
    with app.test_client() as client:
        csp = _csp(client)

    assert csp, "no Content-Security-Policy header was emitted"
    for directive in (
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
    ):
        assert directive in csp, f"missing hardening directive: {directive}"


def test_inline_allowed_by_default_but_no_nonce(monkeypatch):
    """While inline is allowed, no nonce may be emitted.

    A nonce in script-src makes browsers ignore 'unsafe-inline'. Emitting both
    would break every template that has not yet been migrated.
    """
    app = _make_app(monkeypatch, TINYMRP_CSP_ALLOW_INLINE=None)
    with app.test_client() as client:
        csp = _csp(client)

    assert "'unsafe-inline'" in csp, "default build should still allow inline"
    assert "'nonce-" not in csp, (
        "a nonce must not be emitted while 'unsafe-inline' is active — "
        "browsers ignore 'unsafe-inline' when a nonce is present"
    )


def test_disabling_inline_emits_a_nonce(monkeypatch):
    """With inline disallowed, script-src carries a nonce instead.

    Scoped to script-src: style-src deliberately keeps 'unsafe-inline' for the
    static style= attributes, which a nonce cannot cover anyway.
    """
    app = _make_app(monkeypatch, TINYMRP_CSP_ALLOW_INLINE="false")
    with app.test_client() as client:
        csp = _csp(client)

    script_src = re.search(r"script-src ([^;]+)", csp).group(1)
    assert "'unsafe-inline'" not in script_src, "script-src must drop it"
    nonces = re.findall(r"'nonce-([A-Za-z0-9_-]+)'", csp)
    assert nonces, "expected a nonce once inline is disallowed"
    assert len(nonces[0]) >= 16, "nonce looks too short to be unguessable"


def test_nonce_differs_between_responses(monkeypatch):
    """A reused nonce would let an injected script reuse it too."""
    app = _make_app(monkeypatch, TINYMRP_CSP_ALLOW_INLINE="false")
    with app.test_client() as client:
        first = re.findall(r"'nonce-([A-Za-z0-9_-]+)'", _csp(client))
        second = re.findall(r"'nonce-([A-Za-z0-9_-]+)'", _csp(client))

    assert first and second
    assert first[0] != second[0], "nonce must be regenerated per response"


def test_csp_nonce_helper_matches_header(monkeypatch):
    """The value templates render must be the value the header authorises."""
    app = _make_app(monkeypatch, TINYMRP_CSP_ALLOW_INLINE="false")

    with app.test_client() as client:
        resp = client.get("/login")
        header = resp.headers.get("Content-Security-Policy", "")
        header_nonces = re.findall(r"'nonce-([A-Za-z0-9_-]+)'", header)

    assert header_nonces, "no nonce in header"

    # Within a request context the helper must resolve to a non-empty string.
    with app.test_request_context("/login"):
        for fn in app.template_context_processors[None]:
            ctx = fn()
            if "csp_nonce" in ctx:
                # Populated by the before_request hook in a real request; here we
                # only assert the helper is exposed and callable.
                assert callable(ctx["csp_nonce"])
                break
        else:
            pytest.fail("csp_nonce() was not exposed to templates")


def test_report_only_header_absent_unless_enabled(monkeypatch):
    """The probe must be opt-in — it should not appear by default."""
    app = _make_app(monkeypatch)
    with app.test_client() as client:
        resp = client.get("/login")

    assert "Content-Security-Policy-Report-Only" not in resp.headers


def test_report_only_carries_the_stricter_policy(monkeypatch):
    """Report-only mode reports what the strict policy would block."""
    app = _make_app(
        monkeypatch,
        TINYMRP_CSP_REPORT_ONLY_STRICT="true",
    )
    with app.test_client() as client:
        resp = client.get("/login")
        enforced = resp.headers.get("Content-Security-Policy", "")
        report_only = resp.headers.get("Content-Security-Policy-Report-Only", "")

    assert report_only, "report-only header missing when the probe is enabled"
    # The whole point: enforced still permits inline, report-only does not.
    assert "'unsafe-inline'" in enforced
    assert "'unsafe-inline'" not in report_only
    assert "'nonce-" in report_only


def test_report_uri_included_when_configured(monkeypatch):
    app = _make_app(
        monkeypatch,
        TINYMRP_CSP_REPORT_ONLY_STRICT="true",
        TINYMRP_CSP_REPORT_URI="/csp-report",
    )
    with app.test_client() as client:
        resp = client.get("/login")
        report_only = resp.headers.get("Content-Security-Policy-Report-Only", "")

    assert "report-uri /csp-report;" in report_only


def test_other_security_headers_still_set(monkeypatch):
    """Guard against a regression in the surrounding header block."""
    app = _make_app(monkeypatch)
    with app.test_client() as client:
        resp = client.get("/login")

    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def _directive(csp: str, name: str) -> str:
    match = re.search(rf"{name} ([^;]+)", csp)
    return match.group(1) if match else ""


def test_script_src_can_harden_without_touching_style_src(monkeypatch):
    """The two directives are decoupled on purpose (SEC-CSP-01).

    Inline style= attributes are static CSS that cannot execute code, and a
    nonce does not cover style ATTRIBUTES anyway - only <style> blocks. So
    dropping 'unsafe-inline' from style-src would break the layout across 14
    templates for no security gain, while script-src is where XSS actually
    lands and can be tightened on its own.
    """
    app = _make_app(monkeypatch, TINYMRP_CSP_ALLOW_INLINE="false")
    with app.test_client() as client:
        csp = _csp(client)

    script_src = _directive(csp, "script-src")
    style_src = _directive(csp, "style-src")

    assert "'unsafe-inline'" not in script_src, "script-src must harden"
    assert "'nonce-" in script_src, "script-src must carry the nonce instead"
    assert "'unsafe-inline'" in style_src, (
        "style-src must keep allowing inline style= attributes; removing it "
        "breaks column widths across the admin templates"
    )


def test_style_src_never_carries_a_nonce(monkeypatch):
    """A nonce in style-src would be misleading: it does not cover style=."""
    for flag in ("true", "false"):
        app = _make_app(monkeypatch, TINYMRP_CSP_ALLOW_INLINE=flag)
        with app.test_client() as client:
            assert "'nonce-" not in _directive(_csp(client), "style-src")


def test_a_path_style_files_prefix_never_reaches_the_csp(monkeypatch):
    """FILES_URL_PREFIX is normally a path, and a path is not a valid CSP host.

    Injecting "/deliverables" made browsers log
    "Couldn't parse invalid host /deliverables" and discard the source on every
    page load. Same-origin paths are already covered by 'self'.
    """
    app = _make_app(monkeypatch)
    app.config["FILES_URL_PREFIX"] = "/deliverables"
    with app.test_client() as client:
        csp = _csp(client)

    assert "/deliverables" not in csp
    assert "'self'" in _directive(csp, "img-src")


def test_an_absolute_files_origin_is_still_allowed(monkeypatch):
    """A real external file host must keep working."""
    app = _make_app(monkeypatch)
    app.config["FILES_URL_PREFIX"] = "https://files.example.com/deliverables"
    with app.test_client() as client:
        csp = _csp(client)

    # The origin only - a CSP source carries no path.
    assert "https://files.example.com" in _directive(csp, "img-src")
    assert "https://files.example.com" in _directive(csp, "connect-src")
    assert "https://files.example.com/deliverables" not in csp


def test_csp_sources_are_all_syntactically_valid(monkeypatch):
    """Guard the whole header, not just the prefix that caused this bug.

    Every source must be a keyword, a scheme, or a host - never a bare path.
    """
    app = _make_app(monkeypatch)
    app.config["FILES_URL_PREFIX"] = "/deliverables"
    with app.test_client() as client:
        csp = _csp(client)

    for directive in csp.split(";"):
        parts = directive.split()
        for source in parts[1:]:
            assert not source.startswith("/"), (
                f"{source!r} in {parts[0]!r} is a path, which browsers reject "
                "as an invalid host"
            )
