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
