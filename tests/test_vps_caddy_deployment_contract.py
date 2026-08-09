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

    # redis now sits between mongo and app, so stop the slice there or these
    # assertions quietly start covering two services.
    mongo = renderer.split("  mongo:", 1)[1].split("\n  redis:", 1)[0]
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
    assert "urllib.request.urlopen('http://localhost:8000/api/ready', timeout=4)" in app
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


def test_per_instance_compose_ships_redis_so_limits_are_shared_across_workers():
    """OPS-RATE-01.

    Redis reached the single-host compose but never the GUIDED per-instance
    one, so real VPS instances kept counting in memory - which means every
    gunicorn worker held its own counters and the effective limit was the
    configured one multiplied by the worker count.
    """
    common = _read("deploy/scripts/lib/common.sh")
    renderer = _shell_function(common, "render_instance_compose")

    redis = renderer.split("\n  redis:", 1)[1].split("\n  app:", 1)[0]
    app = renderer.split("\n  app:", 1)[1].split("\nnetworks:", 1)[0]

    assert "image: $(redis_image)" in redis
    # Never published, never reachable from the proxy network.
    assert "ports:" not in redis
    assert "      - private" in redis
    assert "      - proxy" not in redis
    # Counters only: persistence off and /data on a tmpfs, so there is no
    # instance state here to back up or restore.
    assert '"--save", ""' in redis
    assert '"--appendonly", "no"' in redis
    assert "      - /data" in redis
    assert "read_only: true" in redis

    # Losing rate limiting is not worth delaying startup for, so the app must
    # not wait on Redis health the way it waits on Mongo.
    assert "condition: service_started" in app


def test_instance_env_points_the_app_at_redis():
    """A Redis nobody connects to is theatre: the app defaults to memory://."""
    created = _read("deploy/scripts/create-instance.sh")
    assert 'RATE_LIMIT_STORAGE_URI="${RATE_LIMIT_STORAGE_URI:-redis://redis:6379/0}"' in created
    assert 'upsert_env_value "$INSTANCE_ENV" "RATE_LIMIT_STORAGE_URI"' in created

    # NEW instances only, deliberately. Two invariants of the update path make
    # retrofitting an existing instance from here wrong:
    #   1. update-instance.sh never writes the instance .env, because rollback
    #      restores the compose file and the container - an env edit would
    #      survive the rollback it was supposed to be undone by.
    #   2. it recreates the app with --no-deps, so an update would never start
    #      the Redis container. Writing the URI there would point a live
    #      instance at a host that does not exist.
    # Migrating an existing instance is therefore an explicit owner action.
    updated = _read("deploy/scripts/update-instance.sh")
    assert 'upsert_env_value "$INSTANCE_ENV"' not in updated


def test_backup_writes_and_verifies_checksums():
    """E7b. The restore drill on 2026-08-07 had to be verified by hand.

    A backup is only trustworthy if you can prove it did not rot between being
    written and being needed. The check runs immediately after writing, so a
    corrupt write fails the backup instead of being discovered during a
    restore - which is the worst possible moment to find out.
    """
    backup = _read("deploy/scripts/backup-instance.sh")

    assert "sha256sum > SHA256SUMS" in backup
    assert "sha256sum --quiet -c SHA256SUMS" in backup
    # Written after the manifest so the manifest is covered by it too.
    assert backup.index("manifest.env") < backup.index("SHA256SUMS")
    # A failed verification must abort, not warn.
    assert 'die "Checksum verification failed' in backup


def test_dns_wait_cannot_hang_an_unattended_install():
    """Found by running the guided installer for real, 2026-08-07.

    The DNS wait loop prompted when a TTY was present and slept forever when it
    was not, so an install driven by CI, a provisioning tool or a plain `ssh
    host cmd` hung indefinitely instead of reporting the mismatch. A hang is
    worse than a failure: nothing tells you why, and no exit code says it went
    wrong. The retry is now bounded and dies with a message naming the escape
    hatch.
    """
    common = _read("deploy/scripts/lib/common.sh")

    assert "DNS_WAIT_MAX_ATTEMPTS" in common
    assert "dns_wait_attempts" in common
    assert "--skip-dns-check to install anyway" in common
    # The interactive path must keep prompting - a human can see what is wrong.
    assert "Press Enter to check again" in common


def test_backup_proves_it_captured_data_and_uses_credentials():
    """Found the hard way: every backup after enabling Mongo auth was EMPTY.

    mongodump without credentials is refused on an authenticated instance. It
    writes a 23-byte gzip header and exits 0. The old guard was
    `[ -s file ] || die`, which asks whether the file has bytes - and an empty
    gzip stream does. Four backups passed that check holding nothing, and one
    of them was taken immediately before updating production.

    A backup that cannot restore is worse than no backup, because it is
    believed. So the check now proves the archive contains documents, and a
    missing deliverables directory fails loudly instead of quietly producing a
    half-backup that reports success.
    """
    backup = _read("deploy/scripts/backup-instance.sh")

    # Credentials are passed when the instance has them.
    assert "MONGO_AUTH_ARGS" in backup
    assert "--authenticationDatabase admin" in backup

    # The guard must measure CONTENT, not file size. It cannot use
    # mongorestore --dryRun: that always reports zero documents because it
    # never reads them, so it would reject good archives too.
    assert 'gzip -dc' in backup
    assert 'essentially no content' in backup
    # The comment above the guard mentions --dryRun to explain why it is not
    # used, so assert it is not INVOKED rather than not mentioned.
    assert 'mongorestore --archive --gzip --dryRun' not in backup
    assert '[ -s "${BACKUP_DIR}/mongo.archive.gz" ] || die' not in backup, (
        "the byte-size guard is back; it passes an archive that restores nothing"
    )

    # A skipped deliverables snapshot must abort, not warn.
    assert "deliverables were requested but the directory is missing" in backup


def test_mongo_healthcheck_is_not_run_every_ten_seconds():
    """mongosh is a full Node REPL, not a light client.

    Measured on the live instance: one invocation costs 1873 ms of CPU and
    opens five connections. At a 10-second interval that is roughly 23 seconds
    of CPU per minute per Mongo container, on an idle host - which was a large
    part of the "40% CPU while idle" the owner reported, spent entirely on
    asking whether the database was alive.
    """
    common = _read("deploy/scripts/lib/common.sh")
    renderer = _shell_function(common, "render_instance_compose")
    mongo = renderer.split("  mongo:", 1)[1].split("\n  redis:", 1)[0]

    assert "mongosh" in mongo, "the check must still prove Mongo answers"
    assert "interval: 10s" not in mongo, (
        "the 10s interval is back; it costs ~23s of CPU per minute per Mongo"
    )
    assert "interval: 30s" in mongo
    # mongosh takes about two seconds, so the timeout has to allow for it.
    assert "timeout: 10s" in mongo
