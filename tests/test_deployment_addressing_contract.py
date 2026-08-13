"""Every install path must tell the application its own address.

`TINYMRP_URL`'s scheme decides whether session cookies are marked `Secure` and
whether the CSP emits `upgrade-insecure-requests`. An installer that creates a
plain-HTTP deployment without declaring it produces an instance nobody can log
into, and the failure is silent - no error, just a login form that keeps coming
back.

These tests read the shell, PowerShell and Compose files without executing
them, so the wiring is checked on every platform. Running the installers for
real is the job of the community-smoke workflow and the release checklist.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# The application must reach the value, not merely have it written to a file
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "compose_file",
    [
        "deploy/community/compose.yaml",
        "docker-compose.yml",
        "docker-compose.onefolder.yml",
    ],
)
def test_compose_files_pass_the_address_into_the_app_container(compose_file):
    """A value that stops at .env never reaches the process that needs it."""
    app_service = _read(compose_file).split("\n  app:", 1)[1]
    assert "TINYMRP_URL:" in app_service, (
        f"{compose_file} does not pass TINYMRP_URL to the app container, so the "
        "app cannot tell whether browsers reach it over TLS"
    )


@pytest.mark.parametrize(
    "compose_file",
    [
        "deploy/community/compose.yaml",
        "docker-compose.yml",
        "docker-compose.onefolder.yml",
    ],
)
def test_compose_files_declare_how_many_proxies_to_trust(compose_file):
    app_service = _read(compose_file).split("\n  app:", 1)[1]
    assert "TINYMRP_TRUSTED_PROXY_HOPS:" in app_service


def test_onefolder_compose_requires_supplied_secrets():
    """This helper predates mandatory secrets and used to boot without any.

    The app no longer generates its own, so an unset SECRET_KEY here is a
    container that will not start - and the compose error should say what to
    run rather than surfacing a Python traceback.
    """
    app_service = _read("docker-compose.onefolder.yml").split("\n  app:", 1)[1]
    assert "SECRET_KEY: ${SECRET_KEY:?" in app_service
    assert "SECURITY_PASSWORD_SALT: ${SECURITY_PASSWORD_SALT:?" in app_service


# --------------------------------------------------------------------------
# Installers must write a scheme that matches the mode they just configured
# --------------------------------------------------------------------------


def test_community_installer_writes_the_address_and_hop_count():
    script = _read("deploy/community/install.sh")
    assert "write_env_value TINYMRP_URL " in script
    assert "write_env_value TINYMRP_TRUSTED_PROXY_HOPS " in script


def test_community_installer_uses_http_for_lan_and_https_for_domain():
    """lan mode must not declare TLS it does not have, and vice versa."""
    script = _read("deploy/community/install.sh")
    assert 'origin="http://$lan_host:$port"' in script
    assert 'origin="https://$domain"' in script


def test_community_installer_only_trusts_a_proxy_in_domain_mode():
    """localhost/lan publish the app port directly - nothing rewrites
    X-Forwarded-For, so believing it hands every client its own rate-limit
    bucket."""
    script = _read("deploy/community/install.sh")
    default_hops = script.index("proxy_hops=0")
    domain_hops = script.index("proxy_hops=1")
    assert default_hops < domain_hops, "the default must be the safe 0"
    assert 'origin="https://$domain"' in script[:domain_hops]


def test_powershell_installer_matches_the_shell_installer():
    script = _read("deploy/community/install.ps1")
    assert "Add-EnvValue $lines TINYMRP_URL $url" in script
    assert "Add-EnvValue $lines TINYMRP_TRUSTED_PROXY_HOPS" in script
    assert "$proxyHops = 0" in script
    assert "$proxyHops = 1" in script


def test_guided_vps_installer_writes_the_instance_address():
    script = _read("deploy/scripts/create-instance.sh")
    assert 'TINYMRP_URL="$INSTANCE_URL"' in script
    assert 'upsert_env_value "$INSTANCE_ENV" "TINYMRP_URL"' in script
    # Caddy fronts every instance and overwrites the forwarded headers.
    assert 'TINYMRP_TRUSTED_PROXY_HOPS="1"' in script


def test_bare_metal_installer_refuses_a_scheme_that_contradicts_its_tls_mode():
    """--http-only with an https:// URL is the exact misconfiguration that
    produces an unbreakable login loop."""
    script = _read("deploy/scripts/install-server.sh")
    assert "--http-only cannot be combined with an https:// --url." in script
    assert "A TLS mode was selected but --url is http://" in script
    assert "TINYMRP_URL=${PUBLIC_URL}" in script


def test_bare_metal_installer_rejects_the_removed_compat_flag():
    """Silently accepting it would imply a security mode that no longer exists."""
    script = _read("deploy/scripts/install-server.sh")
    assert "--compat was removed with compat security mode" in script


# --------------------------------------------------------------------------
# Documentation and templates
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "example",
    [
        ".env.dev.example",
        ".env.docker.example",
        ".env.server.example",
        "deploy/windows/.env.windows.lan.example",
    ],
)
def test_env_examples_declare_the_address(example):
    """A template that omits it teaches the mistake."""
    text = _read(example)
    assert "TINYMRP_URL=" in text
    assert "TINYMRP_TRUSTED_PROXY_HOPS" in text


def test_the_windows_lan_template_the_guide_tells_people_to_copy_exists():
    """docs/help referenced this file for a long time without it being here."""
    template = REPO_ROOT / "deploy/windows/.env.windows.lan.example"
    assert template.is_file()
    text = template.read_text(encoding="utf-8")
    # The four values a Windows LAN operator actually has to supply.
    for required in (
        "TINYMRP_URL=",
        "FILES_LOCAL_ROOT=",
        "SECRET_KEY=",
        "SECURITY_PASSWORD_SALT=",
    ):
        assert required in text


# --------------------------------------------------------------------------
# nginx authorisation subrequests
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "conf",
    [
        "docker/nginx/nginx.conf",
        "deploy/nginx.server.conf",
        "deploy/windows/nginx.lan.conf",
    ],
)
def test_nginx_auth_request_does_not_use_a_variable_in_its_uri(conf):
    """nginx does not expand variables in the auth_request URI.

    "auth_request /files/auth?path=$request_uri" sent the literal text
    "$request_uri" to the app, which answered 403 for every protected file. The
    path has to travel as a header the subrequest location sets instead.
    """
    text = _read(conf)
    # Comments in these files quote the broken form on purpose, so only
    # directives count.
    directives = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    assert "auth_request /files/auth?path=$request_uri" not in directives
    if "auth_request " in directives:
        assert "X-Original-URI $request_uri" in directives, (
            f"{conf} uses auth_request but never forwards the requested path"
        )
