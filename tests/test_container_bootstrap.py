from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from flask_security import hash_password
from flask_security.utils import verify_password

import app as app_module
from app.models.auth import Role, User
from app.services import container_bootstrap
from app.services.container_bootstrap import (
    BootstrapConfigurationError,
    bootstrap_container,
)
from app.services.standard_roles import STANDARD_ROLES, STANDARD_ROLE_SLUGS

ADMIN_ENV = {
    "TINYMRP_SEED_ADMIN": "true",
    "TINYMRP_ADMIN_EMAIL": "owner@example.com",
    "TINYMRP_ADMIN_PASSWORD": "correct-horse-battery-staple",
}


def _existing_user(*, role: Role | None = None) -> User:
    return User(
        email="existing@example.com",
        password="unchanged-hash",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=[role] if role else [],
    ).save()


def test_fresh_bootstrap_creates_exact_canonical_roles_and_administrator(app):
    with app.app_context():
        result = bootstrap_container(ADMIN_ENV)

        assert result["admin"] == "created"
        assert result["roles_created"] == list(STANDARD_ROLE_SLUGS)
        assert set(Role.objects.scalar("name")) == set(STANDARD_ROLE_SLUGS)
        assert Role.objects(name="admin").first() is None

        user = User.objects.get(email="owner@example.com")
        assert user.active is True
        assert [role.name for role in user.roles] == ["administrator"]
        assert verify_password(ADMIN_ENV["TINYMRP_ADMIN_PASSWORD"], user.password)
        assert user.password != ADMIN_ENV["TINYMRP_ADMIN_PASSWORD"]

        for slug, definition in STANDARD_ROLES.items():
            role = Role.objects.get(name=slug)
            assert tuple(role.permissions) == definition.permissions


def test_restart_is_noop_even_when_persisted_seed_credentials_are_absent(app):
    with app.app_context():
        bootstrap_container(ADMIN_ENV)
        before = User.objects.get(email="owner@example.com")
        password_hash = before.password
        role_ids = [str(role.id) for role in before.roles]
        role_count = Role.objects.count()

        result = bootstrap_container({"TINYMRP_SEED_ADMIN": "true"})

        assert result["admin"] == "existing-users-skip"
        assert result["roles_created"] == []
        after = User.objects.get(email="owner@example.com")
        assert after.password == password_hash
        assert [str(role.id) for role in after.roles] == role_ids
        assert Role.objects.count() == role_count


def test_seed_disabled_still_reconciles_roles_without_creating_user(app):
    with app.app_context():
        result = bootstrap_container({"TINYMRP_SEED_ADMIN": "false"})

    assert result["admin"] == "disabled"
    assert set(Role.objects.scalar("name")) == set(STANDARD_ROLE_SLUGS)
    assert User.objects.count() == 0


@pytest.mark.parametrize("legacy_admin", [False, True])
def test_existing_databases_are_preserved(app, legacy_admin):
    with app.app_context():
        role = (
            Role(name="admin", description="Legacy", permissions=[]).save()
            if legacy_admin
            else None
        )
        user = _existing_user(role=role)
        original_roles = [item.name for item in user.roles]

        result = bootstrap_container({"TINYMRP_SEED_ADMIN": "true"})

        user.reload()
        assert result["admin"] == "existing-users-skip"
        assert user.password == "unchanged-hash"
        assert [item.name for item in user.roles] == original_roles
        if legacy_admin:
            assert Role.objects(name="admin").count() == 1


@pytest.mark.parametrize(
    ("environ", "message"),
    [
        ({"TINYMRP_SEED_ADMIN": "true"}, "TINYMRP_ADMIN_EMAIL is required"),
        (
            {
                "TINYMRP_SEED_ADMIN": "true",
                "TINYMRP_ADMIN_EMAIL": "owner@example.com",
            },
            "TINYMRP_ADMIN_PASSWORD is required",
        ),
        (
            {
                "TINYMRP_SEED_ADMIN": "true",
                "TINYMRP_ADMIN_EMAIL": "not-an-email",
                "TINYMRP_ADMIN_PASSWORD": "correct-horse-battery-staple",
            },
            "must be valid",
        ),
        (
            {
                "TINYMRP_SEED_ADMIN": "true",
                "TINYMRP_ADMIN_EMAIL": "owner@example.com",
                "TINYMRP_ADMIN_PASSWORD": "short",
            },
            "at least 12 characters",
        ),
        (
            {
                "TINYMRP_SEED_ADMIN": "true",
                "TINYMRP_ADMIN_EMAIL": "owner@example.com",
                "TINYMRP_ADMIN_PASSWORD": "ChangeMe123!",
            },
            "historical example administrator password is forbidden",
        ),
        ({"TINYMRP_SEED_ADMIN": "sometimes"}, "must be one of true/false"),
    ],
)
def test_invalid_fresh_bootstrap_fails_before_any_database_write(app, environ, message):
    with app.app_context(), pytest.raises(BootstrapConfigurationError, match=message):
        bootstrap_container(environ)

    assert User.objects.count() == 0
    assert Role.objects.count() == 0


def test_role_drift_is_reported_but_not_overwritten_at_boot(app):
    with app.app_context():
        custom = Role(
            name="commercial",
            display_name="Local Commercial",
            description="Site-specific description",
            permissions=["jobs.read"],
        ).save()

        result = bootstrap_container({"TINYMRP_SEED_ADMIN": "false"})

        custom.reload()
        assert result["roles_drifted"] == [
            {
                "slug": "commercial",
                "fields": ["display_name", "description", "permissions"],
            }
        ]
        assert custom.display_name == "Local Commercial"
        assert custom.description == "Site-specific description"
        assert custom.permissions == ["jobs.read"]


def test_reconciliation_failure_propagates_without_creating_user(app, monkeypatch):
    def fail_reconciliation():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(container_bootstrap, "reconcile_standard_roles", fail_reconciliation)
    with app.app_context(), pytest.raises(RuntimeError, match="database unavailable"):
        bootstrap_container(ADMIN_ENV)

    assert User.objects.count() == 0


def test_cli_admin_commands_assign_canonical_role(app):
    with app.app_context():
        _existing_user()
    runner = app.test_cli_runner()

    result = runner.invoke(args=["user", "grant-admin", "--email", "existing@example.com"])

    assert result.exit_code == 0, result.output
    user = User.objects.get(email="existing@example.com")
    assert [role.name for role in user.roles] == ["administrator"]
    assert Role.objects(name="admin").first() is None


def test_cli_bootstrap_admin_uses_shared_credential_validation(app):
    runner = app.test_cli_runner()

    rejected = runner.invoke(
        args=[
            "user",
            "bootstrap-admin",
            "--email",
            "owner@example.com",
            "--password",
            "ChangeMe123!",
        ]
    )

    assert rejected.exit_code != 0
    assert "historical example administrator password is forbidden" in rejected.output
    assert User.objects.count() == 0
    assert Role.objects.count() == 0

    created = runner.invoke(
        args=[
            "user",
            "bootstrap-admin",
            "--email",
            "OWNER@EXAMPLE.COM",
            "--password",
            "correct-horse-battery-staple",
        ]
    )
    assert created.exit_code == 0, created.output
    user = User.objects.get(email="owner@example.com")
    assert [role.name for role in user.roles] == ["administrator"]


def test_configuration_failure_output_never_contains_password(app, monkeypatch, capsys):
    secret = "ChangeMe123!"
    monkeypatch.setattr(app_module, "create_app", lambda: app)
    monkeypatch.setenv("TINYMRP_SEED_ADMIN", "true")
    monkeypatch.setenv("TINYMRP_ADMIN_EMAIL", "owner@example.com")
    monkeypatch.setenv("TINYMRP_ADMIN_PASSWORD", secret)

    assert container_bootstrap.main() == 2

    output = capsys.readouterr()
    assert secret not in output.out
    assert secret not in output.err


def test_entrypoint_is_fail_closed_and_contains_no_inline_seed_logic():
    source = Path("docker/app/entrypoint.sh").read_text(encoding="utf-8")

    assert "python -m app.services.container_bootstrap" in source
    assert "refusing to launch" in source
    assert "continuing to start app" not in source
    assert "Generated one-time admin password" not in source
    assert "PERMISSIONS" not in source
    assert 'upsert("admin"' not in source


def test_direct_compose_defaults_to_no_first_admin_and_requires_credentials():
    main_compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    onefolder_compose = Path("docker-compose.onefolder.yml").read_text(encoding="utf-8")

    assert "TINYMRP_SEED_ADMIN: ${TINYMRP_SEED_ADMIN:-false}" in main_compose
    assert "TINYMRP_SEED_ADMIN: ${TINYMRP_SEED_ADMIN:-false}" in onefolder_compose
    assert "TINYMRP_ADMIN_EMAIL: ${TINYMRP_ADMIN_EMAIL:-}" in onefolder_compose
    assert "TINYMRP_ADMIN_PASSWORD: ${TINYMRP_ADMIN_PASSWORD:-}" in onefolder_compose
    assert "ChangeMe123!" not in main_compose
    assert "ChangeMe123!" not in onefolder_compose


def test_onefolder_helper_generates_credentials_outside_container_logs():
    helper = Path("tools/run-tinymrp-container.ps1").read_text(encoding="utf-8")
    compose = Path("docker-compose.onefolder.yml").read_text(encoding="utf-8")

    assert "RandomNumberGenerator" in helper
    assert '"TINYMRP_SEED_ADMIN=$bootstrapEnabled"' in helper
    assert '"TINYMRP_ADMIN_EMAIL=$AdminEmail"' in helper
    assert '"TINYMRP_ADMIN_PASSWORD=$adminPassword"' in helper
    assert '$bootstrapEnabled = "false"' in helper
    assert "No user or password was changed" in helper
    assert "Generated one-time admin password" not in helper
    assert "logs -n 200 app" not in helper


def test_standalone_installer_uses_safe_idempotent_bootstrap_contract():
    installer = Path("deploy/scripts/install-server.sh").read_text(encoding="utf-8")

    assert "-m app.services.container_bootstrap" in installer
    assert "export TINYMRP_SEED_ADMIN=true" in installer
    assert '"admin": "created"' in installer
    assert '"admin": "existing-users-skip"' in installer
    assert "no password or role assignment was changed" in installer
    assert "Installation did not complete the requested first-administrator bootstrap" in installer
    assert "FLASK_APP=app" not in installer
    assert "--app app user bootstrap-admin --email <email>" in installer
