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


# --------------------------------------------------------------------------
# The Community stack must actually start on a machine that has never run it
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "installer",
    ["deploy/community/install.sh", "deploy/community/install.ps1"],
)
def test_building_from_source_still_pulls_the_third_party_images(installer):
    """--build must not block Mongo, Redis and Caddy from being pulled.

    The app image built from a checkout exists only on that host, so pulling it
    is certain to fail - but `--pull` is a stack-wide flag. Setting it to
    `never` also blocked the three images that DO have to come from a registry,
    so the first --build install on a clean machine died with
    "No such image: mongo:6.0@sha256:..." before a container was created.
    `missing` is the only value that pulls what is absent and leaves the
    locally built image alone.
    """
    text = _read(installer)
    assert "TINYMRP_INSTALL_PULL" in text, f"{installer} no longer sets a pull mode"
    # Only the default assigned after a source build matters. Both scripts also
    # name 'never' when validating an operator-supplied override, which is fine.
    assignments = [
        ':= "${TINYMRP_INSTALL_PULL:=missing}"' in text
        or '${TINYMRP_INSTALL_PULL:=missing}' in text,
        "$env:TINYMRP_INSTALL_PULL = 'missing'" in text,
    ]
    assert any(assignments), (
        f"{installer} does not default the stack-wide pull mode to 'missing' "
        f"after --build; 'never' blocks mongo/redis/caddy on a host that has "
        f"never pulled them"
    )
    assert "${TINYMRP_INSTALL_PULL:=never}" not in text
    assert "$env:TINYMRP_INSTALL_PULL = 'never'" not in text


def test_caddy_keeps_the_capability_its_binary_requires():
    """Domain mode cannot start if Caddy is stripped of NET_BIND_SERVICE.

    /usr/bin/caddy carries a cap_net_bind_service file capability so it can
    bind 80 and 443 without being root. `cap_drop: ALL` empties the bounding
    set, and the kernel then refuses to exec a binary whose permitted file caps
    it cannot grant - the container dies with
    "exec /usr/bin/caddy: operation not permitted" before Caddy logs anything.
    """
    text = _read("deploy/community/compose.yaml")
    caddy = text[text.index("  caddy:") :]
    assert "cap_drop" in caddy, "caddy should still drop capabilities by default"
    assert "NET_BIND_SERVICE" in caddy, (
        "caddy drops ALL capabilities without granting back NET_BIND_SERVICE; "
        "the container cannot exec and domain mode never starts"
    )


def test_caddy_has_a_healthcheck_so_wait_cannot_report_a_dead_proxy():
    """`up --wait` needs something to wait for on the user-facing service.

    Without a healthcheck it accepted a created-but-crash-looping Caddy as
    success, so the installer printed "TinyMRP Community is ready at
    https://..." over a proxy that never served a byte.
    """
    text = _read("deploy/community/compose.yaml")
    caddy = text[text.index("  caddy:") :]
    assert "healthcheck:" in caddy, (
        "caddy has no healthcheck, so `up --wait` cannot tell a working proxy "
        "from a crash-looping one"
    )


def test_operators_can_change_the_address_without_hand_editing_env():
    """The eight addressing keys must be changeable by a supported command.

    They have to agree with each other, and when they do not the symptom is a
    silent login loop rather than an error, so hand-editing .env is a trap.
    """
    text = _read("deploy/community/tinymrp.sh")
    assert "reconfigure)" in text, "tinymrp.sh no longer dispatches `reconfigure`"
    for key in (
        "ACCESS_MODE",
        "APP_BIND_IP",
        "APP_PORT",
        "TINYMRP_URL",
        "TINYMRP_TRUSTED_PROXY_HOPS",
        "TINYMRP_ALLOWED_ORIGINS",
        "TINYMRP_DOMAIN",
        "ACME_EMAIL",
    ):
        assert f"env_set {key} " in text, (
            f"reconfigure does not rewrite {key}, so it can leave the eight "
            f"addressing keys disagreeing"
        )


def test_the_installer_warns_that_an_internal_domain_is_not_publicly_trusted():
    """A .local domain gets a Caddy-signed certificate, not a Let's Encrypt one.

    That is a working HTTPS install, but every browser distrusts it until the
    root certificate is distributed. Finding that out from a browser warning
    instead of from the installer is what costs an afternoon.
    """
    text = _read("deploy/community/install.sh")
    assert "is_internal_domain" in text
    # The classifier itself lives in lib-tls.sh so that the installer,
    # tinymrp.sh and check-install.sh cannot disagree about what is internal.
    shared = _read("deploy/community/lib-tls.sh")
    assert "*.local" in shared, "the internal-domain test no longer covers .local"
    assert "tls_is_internal_domain" in text, (
        "install.sh no longer uses the shared internal-domain classifier"
    )
    assert "root.crt" in text, (
        "the installer never tells an internal-domain operator how to export "
        "the root certificate their clients must trust"
    )


# --------------------------------------------------------------------------
# A checkout-built instance must have a working update path
# --------------------------------------------------------------------------


def test_a_source_built_instance_can_be_updated_without_reinstalling():
    """`update` must not demand a version a source install can never have.

    install.sh --build tags the image <VERSION>-src.<sha>, which exists only on
    that host. The registry path (`compose pull app`) therefore fails every
    time, and requiring a semver argument asks for a tag that was never
    published - so the only documented way to take new code was to reinstall.
    """
    text = _read("deploy/community/tinymrp.sh")
    assert "update_from_source" in text, "tinymrp.sh has no source update path"
    assert "is_source_install" in text, (
        "tinymrp.sh cannot tell a checkout-built install from a released one, "
        "so `update` cannot route to the right path"
    )
    # It has to actually move the checkout and rebuild, not just retag.
    assert "git -C \"$repo_root\" fetch" in text, "source update never fetches"
    assert "merge --ff-only" in text, (
        "source update does not fast-forward; it could create a merge commit "
        "or silently build a diverged tree"
    )
    assert "docker build" in text, "source update never rebuilds the image"
    # Same guarantees as the registry path.
    assert "backup" in text and "wait_for_app" in text


def test_the_source_update_refuses_to_build_an_unreproducible_image():
    """A rebuild bakes the working tree in, so a dirty checkout is refused."""
    text = _read("deploy/community/tinymrp.sh")
    assert "status --porcelain" in text, (
        "source update does not check for uncommitted changes, so it can build "
        "an image that corresponds to no commit"
    )


def test_powershell_has_the_same_source_update_path():
    text = _read("deploy/community/tinymrp.ps1")
    assert "Update-FromSource" in text
    assert "Test-SourceInstall" in text
    assert "merge --ff-only" in text
    assert "status --porcelain" in text


@pytest.mark.parametrize(
    "doc",
    [
        "docs/deployment/01-vm-docker.md",
        "docs/deployment/10-operations.md",
        "deploy/community/README.md",
    ],
)
def test_the_update_path_is_documented_where_people_look(doc):
    """Undocumented, this is indistinguishable from having to reinstall."""
    text = _read(doc)
    assert "tinymrp.sh update" in text, f"{doc} never mentions the update command"
    assert "--build" in text or "git checkout" in text or "checkout" in text, (
        f"{doc} does not distinguish a source install from a release install, "
        f"so a reader cannot tell which update form applies to them"
    )


# --------------------------------------------------------------------------
# The single-install diagnostic
# --------------------------------------------------------------------------


def test_the_community_install_has_a_read_only_diagnostic():
    """Every other deployment path ships a checker; this one did not.

    Windows LAN has check_lan_access.ps1, restricted Windows has
    check-restricted-install.ps1, the VPS has doctor.sh. The single-VM Docker
    path - the recommended one - had nothing, so "it does not work" had no
    first command to run.
    """
    path = REPO_ROOT / "deploy/community/check-install.sh"
    assert path.exists(), "deploy/community/check-install.sh is missing"
    text = path.read_text(encoding="utf-8")
    # It must be read-only in effect: no restart/recreate/build verbs.
    for forbidden in ("up -d", "--force-recreate", "docker build", "env_set", "rm -rf"):
        assert forbidden not in text, (
            f"check-install.sh contains '{forbidden}'; it is documented as "
            f"changing nothing and must stay that way"
        )
    # The checks that matter, each of which corresponds to a real field failure.
    for probe in (
        "TINYMRP_TRUSTED_PROXY_HOPS",   # proxy hops vs access mode
        "ACCESS_MODE=lan but TINYMRP_URL",  # the login-loop trap
        "mountpoint",                    # a share that did not mount
        "/etc/fstab",                    # a share that will not remount at boot
        "/api/ready",                    # database and disk
        "Caddy Local Authority",         # internal vs public certificate
    ):
        assert probe in text, f"check-install.sh no longer checks for {probe}"


def test_the_diagnostic_verifies_writes_rather_than_reading_permissions():
    """`ls` is not evidence on a network share.

    A CIFS mount with uid=1000 displays owner 1000 and mode rwxrwxr-x while the
    file server still refuses every write, because the mount options only
    change what Linux displays. The only meaningful test is an actual write
    from inside the app container.
    """
    text = (REPO_ROOT / "deploy/community/check-install.sh").read_text(encoding="utf-8")
    assert "docker exec" in text and "touch /data/deliverables" in text, (
        "check-install.sh infers deliverables writability instead of writing a "
        "probe file from inside the container"
    )


def test_the_file_share_recipe_carries_the_options_that_matter_at_boot():
    text = _read("docs/deployment/11-faq.md")
    for option in ("_netdev", "nofail", "credentials=", "uid=1000"):
        assert option in text, f"the CIFS recipe lost {option}"
    assert "only changes what Linux *displays*" in text, (
        "the FAQ no longer warns that uid=1000 does not grant write permission"
    )


# --------------------------------------------------------------------------
# Organisation-provided TLS certificates
# --------------------------------------------------------------------------


def test_caddy_can_serve_a_certificate_the_operator_supplies():
    """A LAN deployment behind a company CA must not be forced onto Caddy's own.

    Caddy could previously only obtain a certificate itself: Let's Encrypt for
    a public name, its own authority for an internal one. Organisations that
    already push an internal root CA to every workstation then had to
    distribute a second, unknown authority - or hand-edit the Caddyfile and
    lose it on the next update.
    """
    caddyfile = _read("deploy/community/Caddyfile")
    assert "import /etc/caddy/certs/" in caddyfile, (
        "Caddyfile no longer imports the optional TLS snippet, so a supplied "
        "certificate cannot be served"
    )
    compose = _read("deploy/community/compose.yaml")
    assert "./certs:/etc/caddy/certs:ro" in compose, (
        "the certs directory is not mounted into Caddy, so any certificate "
        "written there is invisible to it"
    )


def test_the_certificate_directory_is_never_committed():
    """A private key in git is a private key on every clone."""
    ignored = _read(".gitignore")
    assert "deploy/community/certs/*" in ignored
    for leaked in ("deploy/community/certs/server.key", "deploy/community/certs/server.crt"):
        assert not (REPO_ROOT / leaked).exists() or leaked in ignored


@pytest.mark.parametrize(
    "script,marker",
    [
        ("deploy/community/lib-tls.sh", "tls_validate_pair"),
        ("deploy/community/lib-tls.ps1", "function Test-TlsPair"),
    ],
)
def test_a_certificate_is_validated_before_it_is_installed(script, marker):
    """Each refusal here is a mistake someone actually makes.

    Handing over the CA root instead of the server certificate is the most
    common by far: it is the file people have to hand, it looks right, and it
    can never work because a root carries no hostname.
    """
    text = _read(script)
    assert marker in text
    for concept in ("CA:TRUE", "CertificateAuthority"):
        if concept in text:
            break
    else:
        pytest.fail(f"{script} does not refuse a CA certificate passed as a server certificate")
    assert "Subject Alternative Name" in text, (
        f"{script} does not require a SAN; browsers ignore the Common Name, so "
        f"a CN-only certificate fails on every client"
    )
    assert "passphrase" in text.lower(), (
        f"{script} accepts an encrypted key, which would make Caddy prompt for "
        f"a passphrase it can never be given and fail every restart"
    )


def test_the_certificate_can_be_replaced_after_installation():
    """Certificates expire; reinstalling the server is not a renewal process."""
    sh = _read("deploy/community/tinymrp.sh")
    assert "set-certificate)" in sh, "tinymrp.sh does not dispatch set-certificate"
    assert "set_certificate()" in sh
    assert "--automatic" in sh, "there is no way back to an automatic certificate"
    ps = _read("deploy/community/tinymrp.ps1")
    assert "'set-certificate'" in ps and "function Set-Certificate" in ps


def test_reconfigure_does_not_silently_keep_a_certificate_for_another_host():
    """Changing the domain invalidates the certificate installed for the old one."""
    text = _read("deploy/community/tinymrp.sh")
    assert "tls_cert_matches_domain" in text, (
        "reconfigure does not re-check the installed certificate against the "
        "new domain, so it could serve one that every client rejects"
    )


def test_the_diagnostic_does_not_call_a_private_ca_a_public_one():
    """It used to report any non-Caddy issuer as a public authority.

    With an organisation's own CA that reads as reassurance where none is due.
    """
    text = _read("deploy/community/check-install.sh")
    assert "TINYMRP_TLS_MODE" in text, "check-install.sh is not aware of the TLS mode"
    assert "organisation-provided certificate" in text
    assert "tls_cert_matches_domain" in text, "it does not verify the SAN covers the domain"
    assert "on the wire is the configured one" in text, (
        "it does not compare the served certificate with the configured file, "
        "so a stale certificate would go unreported"
    )


def test_the_tls_help_separates_docker_from_bare_metal():
    """install-server.sh --cert/--key is the nginx path and does nothing on Docker.

    Presenting it as "your organisation's internal CA" with no qualification
    sent a Docker operator down a path that could not work.
    """
    text = _read("docs/deployment/08-networking-and-tls.md")
    assert "Which installer are you running?" in text, (
        "08-networking-and-tls.md no longer tells the reader which options "
        "apply to their install"
    )
    assert "set-certificate" in text, "the Docker route to a supplied certificate is undocumented"
    assert "bare-metal nginx path only" in text or "bare metal" in text
    # The old hand-edited Caddyfile snippet taught people to do the one thing
    # that gets silently reverted by the next update.
    assert "tls internal\n    reverse_proxy 127.0.0.1:5000" not in text


# --------------------------------------------------------------------------
# The add-in must not infer plaintext for an internal deployment
# --------------------------------------------------------------------------


def test_addin_does_not_downgrade_internal_hostnames_to_http():
    """`BackendUrl=mrp.company.local` used to become http://, token and all.

    Internal names were treated as development hosts, so a configured API token
    crossed the LAN in clear text. A Caddy 80->443 redirect does not save it:
    the first request has already been built and sent.
    """
    text = _read("solidworks-addin/TinyMRP.SolidWorksAddin/Services/NumberingApiClient.cs")
    start = text.index("private static bool IsDevelopmentHost")
    body = text[start:start + 2000]
    for downgraded in ('.EndsWith(".local"', '.EndsWith(".localdomain"', '.EndsWith(".test"'):
        assert downgraded not in body, (
            f"IsDevelopmentHost still treats {downgraded} as a development host, "
            f"so an API token would be sent over plaintext HTTP"
        )
    assert '.localhost' in body, "loopback names should still allow implicit http"
