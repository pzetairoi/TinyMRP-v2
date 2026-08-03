"""Regression contracts for the guided VPS/Caddy deployment path.

These tests intentionally inspect the shell renderers and orchestration order
without executing Docker, changing host state, or requiring Bash.  The release
gate must still run ``docker compose config`` and ``caddy validate`` against the
rendered files on Linux; this module protects the wiring that produces them on
every developer platform.
"""

from __future__ import annotations

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _shell_function(source: str, name: str) -> str:
    marker = f"{name}() {{"
    start = source.index(marker)
    next_function = re.search(r"(?m)^[A-Za-z_][A-Za-z0-9_]*\(\) \{", source[start + len(marker) :])
    end = start + len(marker) + next_function.start() if next_function is not None else len(source)
    return source[start:end]


def _assert_in_order(source: str, *needles: str) -> None:
    cursor = -1
    for needle in needles:
        position = source.find(needle, cursor + 1)
        assert position >= 0, f"missing deployment contract fragment: {needle!r}"
        assert position > cursor
        cursor = position


def test_per_instance_compose_renderer_keeps_mongo_private_and_app_behind_caddy():
    common = _read("deploy/scripts/lib/common.sh")
    renderer = _shell_function(common, "render_instance_compose")

    mongo = renderer.split("  mongo:", 1)[1].split("\n  app:", 1)[0]
    app = renderer.split("\n  app:", 1)[1].split("\nnetworks:", 1)[0]
    networks = renderer.split("\nnetworks:", 1)[1]

    assert "image: $(mongo_image)" in mongo
    assert "ports:" not in mongo
    assert "      - private" in mongo
    assert "      - proxy" not in mongo
    assert "db.adminCommand('ping').ok" in mongo

    assert "image: ${app_image}" in app
    assert "read_only: true" in app
    assert "      - ALL" in app
    assert "env_file:" in app
    assert "      - ${env_file}" in app
    assert "condition: service_healthy" in app
    assert "source: ${deliverables_dir}" in app
    assert "target: /data/deliverables" in app
    assert "urllib.request.urlopen('http://localhost:8000/api/health', timeout=4)" in app
    assert "ports:" not in app
    assert "      - private" in app
    assert "      - proxy" in app

    assert "internal: true" in networks
    assert "external: true" in networks
    assert "name: $(proxy_network_name)" in networks


def test_guided_instance_creation_persists_bootstrap_inputs_before_starting_app():
    create = _read("deploy/scripts/create-instance.sh")

    assert 'FILES_ACCEL_REDIRECT_PREFIX=""' in create
    assert 'TINYMRP_SEED_ADMIN="true"' in create
    assert 'TINYMRP_SECURITY_MODE="${TINYMRP_SECURITY_MODE:-strict}"' in create
    _assert_in_order(
        create,
        'upsert_env_value "$INSTANCE_ENV" "FILES_ACCEL_REDIRECT_PREFIX"',
        'upsert_env_value "$INSTANCE_ENV" "TINYMRP_SEED_ADMIN"',
        'upsert_env_value "$INSTANCE_ENV" "TINYMRP_ADMIN_EMAIL"',
        'upsert_env_value "$INSTANCE_ENV" "TINYMRP_ADMIN_PASSWORD"',
        "write_instance_compose_file \\",
        'docker_compose_file "$INSTANCE_COMPOSE" config -q',
        'docker_compose_file "$INSTANCE_COMPOSE" up -d --build',
        'wait_for_container_ready "$APP_CONTAINER_NAME" 300',
        'install_caddy_route "tinymrp-${INSTANCE_NAME}" "$DOMAIN" "$APP_CONTAINER_NAME" "8000"',
    )

    # The generated app is reached only through the shared proxy network; the
    # create path must not fall back to an Nginx-only accelerated-file route.
    assert "ensure_proxy_network" in create
    assert 'FILES_ACCEL_REDIRECT_PREFIX="/__files"' not in create


def test_caddy_renderer_validates_and_restores_routes_before_reload():
    common = _read("deploy/scripts/lib/common.sh")
    root_renderer = _shell_function(common, "render_caddy_root_config")
    route_renderer = _shell_function(common, "render_caddy_route")
    installer = _shell_function(common, "install_caddy_route")

    assert "import /etc/caddy/routes/*.caddy" in root_renderer
    assert 'site_label="http://${domain}"' in route_renderer
    assert 'site_label="https://${domain}"' in route_renderer
    assert "tls internal" in route_renderer
    assert "?Strict-Transport-Security" in route_renderer
    assert "?X-Content-Type-Options" in route_renderer
    assert "?Referrer-Policy" in route_renderer
    assert "?X-Frame-Options" in route_renderer
    assert "reverse_proxy %s:%s" in route_renderer
    assert "www.%s" in route_renderer

    _assert_in_order(
        installer,
        'render_caddy_route "$domain" "$upstream_host" "$upstream_port"',
        'cp "$route_file" "$backup_file"',
        'mv "$tmp_file" "$route_file"',
        "if ! validate_caddy_config; then",
        'mv "$backup_file" "$route_file"',
        'die "Caddy route update failed."',
        "reload_caddy",
    )


def test_update_preserves_caddy_env_and_rolls_back_each_failed_verification():
    update = _read("deploy/scripts/update-instance.sh")

    assert 'REVERSE_PROXY:-}" = "caddy"' in update
    assert 'FILES_ACCEL_REDIRECT_PREFIX:-}"' in update
    assert "Clear it before updating" in update
    assert 'upsert_env_value "$INSTANCE_ENV"' not in update
    assert "install_caddy_route" not in update
    assert "reload_caddy" not in update

    _assert_in_order(
        update,
        "write_instance_compose_file \\",
        'docker_compose_file "$DESIRED_COMPOSE" config -q',
        'mv "$DESIRED_COMPOSE" "$INSTANCE_COMPOSE"',
        'docker_compose_file "$INSTANCE_COMPOSE" up -d --no-deps --force-recreate app',
        'wait_for_container_ready "$APP_CONTAINER_NAME" "$HEALTH_TIMEOUT"',
        'endpoint_responds "${INSTANCE_DOMAIN}" "${TLS_MODE}"',
        'api_health_responds "${INSTANCE_DOMAIN}" "${TLS_MODE}"',
        '"${SCRIPT_DIR}/doctor.sh" --instance "$INSTANCE_NAME" --skip-host-checks',
        'write_instance_current_state "$INSTANCE_NAME"',
    )

    for trigger in (
        "compose-up",
        "container-health",
        "public-endpoint",
        "api-health",
        "doctor",
    ):
        assert f'rollback_from_backup "{trigger}"' in update


def test_manual_rollback_revalidates_restored_app_through_existing_caddy_route():
    rollback = _read("deploy/scripts/rollback-instance.sh")

    assert 'upsert_env_value "$INSTANCE_ENV"' not in rollback
    assert "install_caddy_route" not in rollback
    assert "reload_caddy" not in rollback
    _assert_in_order(
        rollback,
        'cp -a "$SOURCE_BACKUP_COMPOSE_FILE" "$INSTANCE_COMPOSE"',
        'docker_compose_file "$INSTANCE_COMPOSE" config -q',
        'docker_compose_file "$INSTANCE_COMPOSE" up -d --no-deps --force-recreate app',
        'wait_for_container_ready "$APP_CONTAINER_NAME" "$HEALTH_TIMEOUT"',
        'endpoint_responds "${INSTANCE_DOMAIN}" "${TLS_MODE}"',
        '"${SCRIPT_DIR}/doctor.sh" --instance "$INSTANCE_NAME" --skip-host-checks',
        'write_instance_current_state "$INSTANCE_NAME"',
    )


def test_doctor_checks_the_live_caddy_file_contract_and_routed_health():
    doctor = _read("deploy/scripts/doctor.sh")
    check_instance = _shell_function(doctor, "check_instance")

    assert (
        'container_env_value_live "${APP_CONTAINER_NAME}" "FILES_ACCEL_REDIRECT_PREFIX"'
        in check_instance
    )
    assert 'REVERSE_PROXY:-}" = "caddy"' in check_instance
    assert "X-Accel-Redirect is Nginx-only" in check_instance
    assert 'route_file="$(caddy_routes_dir)/tinymrp-${INSTANCE_NAME}.caddy"' in check_instance
    assert 'route_target="reverse_proxy ${APP_CONTAINER_NAME}:8000"' in check_instance
    assert 'endpoint_responds "${INSTANCE_DOMAIN}" "${TLS_MODE}"' in check_instance
    assert 'api_health_responds "${INSTANCE_DOMAIN}" "${TLS_MODE}"' in check_instance
    assert 'docker port "${MONGO_CONTAINER_NAME}" 27017' in check_instance
