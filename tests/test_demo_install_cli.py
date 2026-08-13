"""`flask demo install` — the one command that makes a fresh install testable.

A new deployment has canonical roles and a single administrator and nothing to
look at. Evaluating whether roles, scopes and file access behave requires a
dataset plus one login per role scenario, which previously existed only behind
the admin UI. That is unusable from an install script, a VM image build, or a
support session over SSH.
"""

from __future__ import annotations

import json

from app.models.auth import User
from app.services.app_settings import permission_test_data_enabled
from app.services.sample_dataset import PART_NUMBER, load_sample_manifest


def _result_json(result):
    """Parse stdout only.

    The reminder to delete these accounts goes to stderr on purpose, so that
    `flask demo install > credentials.json` yields a clean file. Click's test
    runner interleaves the two streams, so decode the leading object and ignore
    whatever the runner appended.
    """
    assert result.exit_code == 0, result.output
    payload, _ = json.JSONDecoder().raw_decode(result.output.lstrip())
    return payload


def test_demo_install_copies_files_seeds_users_and_prints_passwords(app, tmp_path):
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    report = _result_json(
        app.test_cli_runner().invoke(args=["demo", "install", "--deliverables", str(tmp_path)])
    )

    expected_files = len(load_sample_manifest()["managed_files"])
    assert report["files"]["copied"] == expected_files
    assert report["deliverables_root"] == str(tmp_path)

    # Every seeded scenario must be usable: an address, a password to type, and
    # the roles it is meant to demonstrate.
    assert report["users"], "no demo users were seeded"
    for row in report["users"]:
        assert row["email"].endswith("@demo.com")
        assert row["password"]
        assert isinstance(row["roles"], list)
    assert User.objects(email__endswith="@demo.com").count() == len(report["users"])

    # The sample part family is what the demo logins are scoped against.
    assert report["counts"]["parts_total"] >= 1
    assert report["counts"]["sample_parts"] >= 1


def test_demo_install_turns_on_the_admin_ui_controls(app, tmp_path):
    """Seeding data the dashboard then refuses to show is a confusing half-state."""
    assert permission_test_data_enabled() is False
    app.test_cli_runner().invoke(args=["demo", "install", "--deliverables", str(tmp_path)])
    assert permission_test_data_enabled() is True


def test_demo_install_is_repeatable_without_duplicating_files_or_users(app, tmp_path):
    runner = app.test_cli_runner()
    first = _result_json(runner.invoke(args=["demo", "install", "--deliverables", str(tmp_path)]))
    second = _result_json(runner.invoke(args=["demo", "install", "--deliverables", str(tmp_path)]))

    assert second["files"]["copied"] == 0
    assert second["files"]["skipped"] == first["files"]["copied"]
    assert User.objects(email__endswith="@demo.com").count() == len(first["users"])
    # Re-running rotates credentials rather than leaving stale ones valid.
    assert {row["password"] for row in second["users"]} != {
        row["password"] for row in first["users"]
    }


def test_demo_install_needs_a_destination(app):
    app.config["FILES_LOCAL_ROOT"] = ""
    app.config["FILE_ROOT_LOCAL"] = ""
    result = app.test_cli_runner().invoke(args=["demo", "install"])
    assert result.exit_code != 0
    assert "FILES_LOCAL_ROOT" in result.output


def test_demo_remove_deletes_the_logins_it_created(app, tmp_path):
    runner = app.test_cli_runner()
    runner.invoke(args=["demo", "install", "--deliverables", str(tmp_path)])
    assert User.objects(email__endswith="@demo.com").count() > 0

    report = _result_json(runner.invoke(args=["demo", "remove", "--disable"]))

    assert User.objects(email__endswith="@demo.com").count() == 0
    assert report["disabled"] is True
    assert permission_test_data_enabled() is False
    # Files stay: by now they may be imported, annotated or linked.
    assert (tmp_path / load_sample_manifest()["managed_files"][0]["path"]).is_file()


def test_demo_dataset_is_the_documented_cv03_family(app, tmp_path):
    """The docs name this part number; keep the command and the docs agreeing."""
    from app.models.part import Part

    app.test_cli_runner().invoke(args=["demo", "install", "--deliverables", str(tmp_path)])
    assert Part.objects(part_number=PART_NUMBER).first() is not None
