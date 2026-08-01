import json
import uuid

import pytest
from mongoengine.errors import ValidationError

from app.models.auth import Role, User
from app.services.standard_roles import STANDARD_ROLES, STANDARD_ROLE_SLUGS


def _result_json(result):
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_seed_roles_creates_all_standard_roles_with_exact_contents(app):
    runner = app.test_cli_runner()
    report = _result_json(runner.invoke(args=["user", "seed-roles"]))

    assert report["mode"] == "create-missing"
    assert report["created"] == list(STANDARD_ROLE_SLUGS)
    assert Role.objects.count() == len(STANDARD_ROLE_SLUGS)

    for slug, definition in STANDARD_ROLES.items():
        role = Role.objects.get(name=slug)
        assert role.display_name == definition.display_name
        assert role.description == definition.description
        assert tuple(role.permissions) == definition.permissions


def test_seed_roles_is_idempotent_and_does_not_assign_users(app):
    user = User(
        email="unassigned@example.com",
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
    ).save()
    runner = app.test_cli_runner()

    _result_json(runner.invoke(args=["user", "seed-roles"]))
    report = _result_json(runner.invoke(args=["user", "seed-roles"]))

    assert report["created"] == []
    assert report["drifted"] == []
    assert report["unchanged"] == list(STANDARD_ROLE_SLUGS)
    user.reload()
    assert user.roles == []


def test_seed_roles_reports_drift_without_overwriting_customisation(app):
    custom = Role(
        name="commercial",
        display_name="Custom Planner",
        description="Locally customised",
        permissions=["jobs.read"],
    ).save()
    runner = app.test_cli_runner()

    report = _result_json(runner.invoke(args=["user", "seed-roles"]))

    assert report["created"] == [
        slug for slug in STANDARD_ROLE_SLUGS if slug != "commercial"
    ]
    assert report["drifted"] == [
        {
            "fields": ["display_name", "description", "permissions"],
            "slug": "commercial",
        }
    ]
    assert report["updated"] == []
    custom.reload()
    assert custom.display_name == "Custom Planner"
    assert custom.description == "Locally customised"
    assert custom.permissions == ["jobs.read"]


def test_seed_roles_dry_run_performs_no_writes(app):
    runner = app.test_cli_runner()

    report = _result_json(runner.invoke(args=["user", "seed-roles", "--dry-run"]))

    assert report["mode"] == "dry-run"
    assert report["missing"] == list(STANDARD_ROLE_SLUGS)
    assert Role.objects.count() == 0


def test_seed_roles_apply_replaces_only_canonical_role_fields(app):
    custom = Role(
        name="commercial",
        display_name="Custom Planner",
        description="Locally customised",
        permissions=["jobs.read"],
    ).save()
    user = User(
        email="planner@example.com",
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=[custom],
    ).save()
    runner = app.test_cli_runner()

    report = _result_json(runner.invoke(args=["user", "seed-roles", "--apply"]))

    assert report["mode"] == "apply"
    assert report["updated"] == ["commercial"]
    custom.reload()
    definition = STANDARD_ROLES["commercial"]
    assert custom.display_name == definition.display_name
    assert custom.description == definition.description
    assert tuple(custom.permissions) == definition.permissions
    user.reload()
    assert [role.name for role in user.roles] == ["commercial"]


def test_seed_roles_rejects_conflicting_modes(app):
    runner = app.test_cli_runner()

    result = runner.invoke(args=["user", "seed-roles", "--dry-run", "--apply"])

    assert result.exit_code != 0
    assert "--dry-run and --apply cannot be used together" in result.output


def test_reconciliation_reports_historical_invalid_permissions_without_rewriting(app):
    Role._get_collection().insert_one(
        {
            "name": "historical_custom",
            "description": "Historical role",
            "permissions": [
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "historical.unknown",
        ],
        }
    )
    historical = Role.objects.get(name="historical_custom")
    assert historical.permissions == [
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "historical.unknown",
        ]

    runner = app.test_cli_runner()
    report = _result_json(runner.invoke(args=["user", "seed-roles", "--dry-run"]))

    assert report["invalid_permissions"] == [
        {
            "duplicates": [],
            "slug": "historical_custom",
            "unknown": ["historical.unknown"],
        }
    ]
    assert report["removed_permissions"] == [
        {"permissions": ["historical.unknown"], "slug": "historical_custom"}
    ]
    historical.reload()
    assert historical.permissions == [
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "historical.unknown",
        ]
    historical.description = "Attempted edit"
    with pytest.raises(ValidationError, match="historical.unknown"):
        historical.save()
