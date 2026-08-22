"""Issue #18: the add-in's upload packs accumulate in <deliverables>/bom forever.

One live estate held 1,258 of them, 281 MB, the oldest eighteen months old.
Nothing reads them after their import, so they are moved aside - never deleted,
because the pack is the only record of what was imported.
"""

import os
import time
from datetime import timedelta
from pathlib import Path

from app.models.app_settings import AppSettings
from app.services.app_settings import get_app_settings
from app.services.bom_packs import (
    archive_old_bom_packs,
    sweep_bom_packs_if_due,
)
from app.services.timezone_utils import utc_now


def _pack(root: Path, name: str, *, age_days: float) -> Path:
    bom = root / "bom"
    bom.mkdir(parents=True, exist_ok=True)
    path = bom / name
    path.write_bytes(b"PK\x03\x04 pretend pack")
    stamp = time.time() - age_days * 86400
    os.utime(path, (stamp, stamp))
    return path


def _configure(app, root: Path) -> None:
    app.config["FILE_ROOT_LOCAL"] = str(root)
    app.config["FILES_LOCAL_ROOT"] = str(root)


def test_old_packs_are_archived_and_recent_ones_left_alone(app, tmp_path):
    with app.app_context():
        _configure(app, tmp_path)
        old = _pack(tmp_path, "OLD_REV__2025_01_01.zip", age_days=30)
        recent = _pack(tmp_path, "NEW_REV__2026_08_21.zip", age_days=2)

        report = archive_old_bom_packs(7)

        assert report["archived"] == 1
        assert not old.exists()
        assert (tmp_path / "bom" / "archive" / old.name).is_file()
        assert recent.is_file(), "a pack inside the window must not move"


def test_nothing_is_ever_deleted(app, tmp_path):
    """The bytes must survive the sweep; only their location changes."""
    with app.app_context():
        _configure(app, tmp_path)
        old = _pack(tmp_path, "KEEP_REV__2025_01_01.zip", age_days=400)
        payload = old.read_bytes()

        archive_old_bom_packs(7)

        archived = tmp_path / "bom" / "archive" / old.name
        assert archived.read_bytes() == payload


def test_the_archive_is_never_swept_into_itself(app, tmp_path):
    with app.app_context():
        _configure(app, tmp_path)
        archive = tmp_path / "bom" / "archive"
        archive.mkdir(parents=True, exist_ok=True)
        already = archive / "ALREADY_REV_.zip"
        already.write_bytes(b"PK\x03\x04")
        stamp = time.time() - 400 * 86400
        os.utime(already, (stamp, stamp))

        report = archive_old_bom_packs(7)

        assert report["archived"] == 0
        assert already.is_file()
        assert not (archive / "archive").exists()


def test_a_repeated_filename_does_not_overwrite_an_archived_pack(app, tmp_path):
    with app.app_context():
        _configure(app, tmp_path)
        archive = tmp_path / "bom" / "archive"
        archive.mkdir(parents=True, exist_ok=True)
        (archive / "SAME_REV_.zip").write_bytes(b"first")
        _pack(tmp_path, "SAME_REV_.zip", age_days=30).write_bytes(b"second")
        os.utime(
            tmp_path / "bom" / "SAME_REV_.zip",
            (time.time() - 30 * 86400,) * 2,
        )

        archive_old_bom_packs(7)

        assert (archive / "SAME_REV_.zip").read_bytes() == b"first"
        assert (archive / "SAME_REV_.1.zip").read_bytes() == b"second"


def test_non_zip_files_are_never_touched(app, tmp_path):
    with app.app_context():
        _configure(app, tmp_path)
        bom = tmp_path / "bom"
        bom.mkdir(parents=True, exist_ok=True)
        stray = bom / "notes.txt"
        stray.write_text("keep me")
        os.utime(stray, (time.time() - 400 * 86400,) * 2)

        archive_old_bom_packs(7)

        assert stray.is_file()


def test_retention_of_zero_disables_the_sweep(app, tmp_path):
    with app.app_context():
        _configure(app, tmp_path)
        old = _pack(tmp_path, "OFF_REV_.zip", age_days=400)

        assert archive_old_bom_packs(0)["archived"] == 0
        assert old.is_file()


def test_sweep_runs_once_a_day_at_most(app, tmp_path):
    with app.app_context():
        _configure(app, tmp_path)
        AppSettings.objects.delete()
        _pack(tmp_path, "FIRST_REV_.zip", age_days=30)

        first = sweep_bom_packs_if_due()
        _pack(tmp_path, "SECOND_REV_.zip", age_days=30)
        second = sweep_bom_packs_if_due()

        assert first["ran"] == 1 and first["archived"] == 1
        assert second["ran"] == 0, "a second import the same day must not re-sweep"
        assert (tmp_path / "bom" / "SECOND_REV_.zip").is_file()

        # A day later it is due again.
        settings = get_app_settings()
        settings.update(set__bom_pack_swept_at=utc_now() - timedelta(days=1, minutes=1))
        third = sweep_bom_packs_if_due()
        assert third["ran"] == 1 and third["archived"] == 1


def test_a_missing_bom_folder_is_not_an_error(app, tmp_path):
    with app.app_context():
        _configure(app, tmp_path)
        assert archive_old_bom_packs(7) == {"archived": 0, "failed": 0, "scanned": 0}
