"""The backups dashboard reports; it must never write, and never 500.

A production instance was found running with no scheduled backup at all and
nobody noticed, because nothing surfaced it. These tests pin the two properties
that make the dashboard worth having: it tells the truth about an empty or
missing backup directory instead of erroring, and it flags an archive that is
too small to contain documents - the exact shape of the silent failure that
went unnoticed here for weeks.
"""
from __future__ import annotations

import gzip
import os

import pytest

from app.services import backups


@pytest.fixture
def backups_dir(tmp_path, monkeypatch):
    target = tmp_path / "backups"
    target.mkdir()
    monkeypatch.setattr(backups, "BACKUPS_DIR", str(target))
    return target


def _make_backup(root, name: str, archive_bytes: bytes) -> None:
    d = root / name
    d.mkdir()
    with gzip.open(d / "mongo.archive.gz", "wb") as fh:
        fh.write(archive_bytes)


def test_missing_directory_reports_unavailable_rather_than_raising(monkeypatch, tmp_path):
    monkeypatch.setattr(backups, "BACKUPS_DIR", str(tmp_path / "definitely-not-here"))
    assert backups.backups_available() is False
    assert backups.list_backups() == []
    result = backups.summary()
    assert result["available"] is False
    assert result["count"] == 0
    assert result["latest"] is None


def test_empty_directory_is_available_but_has_no_backups(backups_dir):
    result = backups.summary()
    assert result["available"] is True
    assert result["count"] == 0
    assert result["total_bytes"] == 0


def test_backups_are_listed_newest_first(backups_dir):
    _make_backup(backups_dir, "20260101-000000", b"x" * 5000)
    _make_backup(backups_dir, "20260808-000000", b"x" * 5000)
    _make_backup(backups_dir, "20260404-000000", b"x" * 5000)

    names = [row["name"] for row in backups.list_backups()]
    assert names == ["20260808-000000", "20260404-000000", "20260101-000000"]


def test_a_tiny_archive_is_flagged_as_looking_empty(backups_dir):
    """mongodump writes a valid, tiny archive and exits 0 when it cannot
    authenticate. Four consecutive backups here were empty that way."""
    _make_backup(backups_dir, "20260808-000000", b"")
    _make_backup(backups_dir, "20260807-000000", b"y" * 20000)

    rows = {row["name"]: row for row in backups.list_backups()}
    assert rows["20260808-000000"]["looks_empty"] is True
    assert rows["20260807-000000"]["looks_empty"] is False


def test_sizes_and_totals_are_reported(backups_dir):
    _make_backup(backups_dir, "20260808-000000", b"z" * 40000)
    result = backups.summary()
    assert result["count"] == 1
    assert result["total_bytes"] > 0
    assert result["latest"]["name"] == "20260808-000000"


def test_disk_usage_reports_real_numbers(backups_dir):
    usage = backups.disk_usage()
    assert usage is not None
    assert usage["total_bytes"] > 0
    assert usage["free_bytes"] >= 0
    assert usage["used_bytes"] + usage["free_bytes"] <= usage["total_bytes"] + 1


def test_listing_never_writes_to_the_backups_directory(backups_dir):
    """The mount is read-only in production; anything that writes would fail
    there and pass here, so pin it."""
    _make_backup(backups_dir, "20260808-000000", b"q" * 3000)
    before = sorted(os.listdir(backups_dir))
    backups.summary()
    backups.list_backups()
    assert sorted(os.listdir(backups_dir)) == before


# --- what a backup holds, and where it went ---------------------------------
#
# Deliverables are the expensive half and are off by default. When they are
# turned on they can be written to another drive, in which case the backup
# folder holds only a pointer. The dashboard has to describe that accurately:
# an operator deciding whether they are covered needs to know what each backup
# contains, not just how big the folder is.


def _backup(backups_dir, name: str, *, manifest: str = "", deliverables: bool = False):
    path = backups_dir / name
    path.mkdir()
    with gzip.open(path / "mongo.archive.gz", "wb") as handle:
        handle.write(b"x" * 4096)
    if deliverables:
        (path / "deliverables.tar.gz").write_bytes(b"y" * 2048)
    if manifest:
        (path / "manifest.env").write_text(manifest, encoding="utf-8")
    return path


def test_a_database_only_backup_is_reported_as_such(backups_dir):
    _backup(backups_dir, "20260101-000000")

    row = backups.list_backups()[0]

    assert row["kind"] == "database"
    assert row["deliverables_elsewhere"] == ""


def test_deliverables_in_the_folder_make_it_a_full_backup(backups_dir):
    _backup(backups_dir, "20260101-000000", deliverables=True)

    row = backups.list_backups()[0]

    assert row["kind"] == "full"


def test_deliverables_on_another_drive_still_count_as_a_full_backup(backups_dir):
    """The folder holds a pointer, not the archive.

    Classifying by the local file alone would call this database-only, and the
    dashboard would tell an operator they have no file backup when they do.
    """
    _backup(
        backups_dir,
        "20260101-000000",
        manifest="DELIVERABLES_ARCHIVE=/mnt/backup/inst/20260101-000000/deliverables.tar.gz\nDELIVERABLES_BYTES=2048\n",
    )

    row = backups.list_backups()[0]

    assert row["kind"] == "full"
    assert row["deliverables_elsewhere"].startswith("/mnt/backup/")
    assert row["deliverables_bytes"] == 2048


def test_the_summary_counts_each_kind_and_the_off_drive_cost(backups_dir):
    _backup(backups_dir, "20260101-000000")
    _backup(backups_dir, "20260102-000000", deliverables=True)
    _backup(
        backups_dir,
        "20260103-000000",
        manifest="DELIVERABLES_ARCHIVE=/mnt/backup/x.tar.gz\nDELIVERABLES_BYTES=5000\n",
    )

    report = backups.summary()

    assert report["count"] == 3
    assert report["full_count"] == 2
    assert report["database_count"] == 1
    assert report["offsite_bytes"] == 5000
    assert report["latest_full"]["name"] == "20260103-000000"


def test_the_policy_defaults_to_database_only(app):
    """Nothing configured must mean deliverables are NOT backed up."""
    with app.app_context():
        policy = backups.effective_policy()

    assert policy["database_included"] is True
    assert policy["deliverables_included"] is False


def test_the_policy_reports_where_deliverables_go(app):
    from app.models.app_settings import AppSettings

    with app.app_context():
        AppSettings(
            backup_include_deliverables=True,
            backup_deliverables_frequency="fortnightly",
            backup_deliverables_dest="/mnt/backupdrive",
        ).save()

        policy = backups.effective_policy()

    assert policy["deliverables_included"] is True
    assert policy["deliverables_frequency_label"] == "every two weeks"
    assert policy["deliverables_destination"] == "/mnt/backupdrive"
    assert policy["deliverables_offsite"] is True


def test_deliverables_beside_the_database_are_flagged_as_not_offsite(app):
    """A backup on the same disk as the data protects against a mistake only."""
    from app.models.app_settings import AppSettings

    with app.app_context():
        AppSettings(backup_include_deliverables=True, backup_deliverables_dest="").save()

        policy = backups.effective_policy()

    assert policy["deliverables_included"] is True
    assert policy["deliverables_offsite"] is False


def test_the_summary_survives_unreadable_settings(backups_dir, monkeypatch):
    """The panel is diagnostic; it must render when things are broken."""
    def _boom():
        raise RuntimeError("no database")

    monkeypatch.setattr(backups, "effective_policy", _boom)
    _backup(backups_dir, "20260101-000000")

    report = backups.summary()

    assert report["policy"] is None
    assert report["count"] == 1


# --- the page has to be reachable, and gated -------------------------------


def _admin(app, permissions):
    from app.models.auth import Role, User
    import uuid

    role = Role(name=f"backup-role-{uuid.uuid4()}", permissions=list(permissions)).save()
    return User(
        email=f"{uuid.uuid4()}@example.com",
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=[role],
    ).save()


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def test_the_backups_page_renders_with_real_backups_present(client, app, backups_dir):
    """The populated path, which is the one that actually ships.

    An earlier version of this test asserted only that the page returned 200,
    with no backups directory present - so it took the empty branch every time
    and never rendered a single size. The page shipped calling a macro that did
    not exist there and 500'd on the first instance that had backups.
    """
    _backup(backups_dir, "20260101-000000")
    _backup(
        backups_dir,
        "20260102-000000",
        manifest="DELIVERABLES_ARCHIVE=/mnt/backupdrive/x.tar.gz\nDELIVERABLES_BYTES=2048\n",
    )
    with app.app_context():
        user = _admin(app, ["system.maintenance", "system.config.read"])
    _login(client, user)

    response = client.get("/admin/backups")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "What gets backed up" in body
    assert "20260102-000000" in body, "the backups themselves must be listed"
    assert "Database + files" in body and "Database only" in body, (
        "each backup must say what it holds"
    )
    assert "/mnt/backupdrive/" in body, "an off-drive archive must say where it is"
    assert "restore-instance.sh" in body, (
        "the page must show how to restore, since it deliberately has no button"
    )
    assert "B</" in body or "KB" in body or "MB" in body, (
        "sizes must actually render; this is what the 500 was"
    )


def test_the_backups_page_is_gated(client, app):
    with app.app_context():
        user = _admin(app, ["parts.read"])
    _login(client, user)

    assert client.get("/admin/backups").status_code == 403


def test_the_backups_page_survives_an_unreadable_backup_directory(client, app, monkeypatch):
    """A moved directory must not take the page down."""
    def _boom(*_args, **_kwargs):
        raise OSError("gone")

    monkeypatch.setattr(backups, "summary", _boom)
    with app.app_context():
        user = _admin(app, ["system.maintenance"])
    _login(client, user)

    response = client.get("/admin/backups")

    assert response.status_code == 200
    assert "No backups directory" in response.get_data(as_text=True)


def test_the_admin_navigation_links_to_backups(client, app):
    """Buried on a page nobody visits is the same as not existing."""
    with app.app_context():
        user = _admin(app, ["system.maintenance", "system.config.read"])
    _login(client, user)

    body = client.get("/admin/backups").get_data(as_text=True)

    assert "/admin/backups" in body
    assert ">Backups</a>" in body, "no navigation entry points at the page"


def test_the_admin_dashboard_offers_backups_alongside_the_other_tools(client, app):
    """Backups was the only thing on that page that was not a tile.

    It was a table bolted below the grid, which is both inconsistent and where
    nobody looks. It is a tile in "System & danger zone" now, next to Metrics
    and Rescan, and the overview only interrupts when something is wrong.
    """
    with app.app_context():
        user = _admin(app, ["system.maintenance", "system.config.read"])
    _login(client, user)

    body = client.get("/admin/").get_data(as_text=True)

    assert "/admin/backups" in body, "the dashboard does not offer Backups at all"
    assert "Rescan part files" in body, "the System tiles should be unchanged"
    assert "<table" not in body.split("System &")[-1], (
        "the overview should not be listing backups again; that is the "
        "Backups page's job"
    )
