"""Imports must not break because staging lands on another filesystem.

Found on a real deployment: EVERY import that wrote a file failed with
"cross-store file commit failed at <part>".

_commit_files finishes with os.replace, which is atomic but cannot cross a
filesystem boundary - it raises EXDEV. The hardened container runs a read-only
root with a tmpfs /tmp, so the system temp directory is a DIFFERENT DEVICE from
the bind-mounted deliverables volume. Measured on the instance: /tmp was device
162 and /data/deliverables device 2065.

The fix is to stage on the destination's filesystem rather than to give up
atomicity by copying - a partial copy would leave a truncated file where a
whole one used to be.
"""

from __future__ import annotations

import os

from app.services.upload_pack import _make_stage_root


def test_staging_shares_a_device_with_the_destination(tmp_path):
    file_root = tmp_path / "deliverables"
    file_root.mkdir()

    stage = _make_stage_root(str(file_root))

    assert os.stat(stage).st_dev == os.stat(file_root).st_dev, (
        "staging must sit on the destination filesystem or os.replace raises EXDEV"
    )
    assert os.path.dirname(stage) == str(file_root)


def test_the_staging_directory_stays_out_of_the_way_of_scans(tmp_path):
    file_root = tmp_path / "deliverables"
    file_root.mkdir()

    stage = _make_stage_root(str(file_root))

    assert os.path.basename(stage).startswith("."), "a visible temp dir would be scanned as content"


def test_a_missing_file_root_is_created_rather_than_fatal(tmp_path):
    file_root = tmp_path / "not-yet-there"

    stage = _make_stage_root(str(file_root))

    assert os.path.isdir(stage)
    assert os.stat(stage).st_dev == os.stat(file_root).st_dev


def test_no_file_root_still_yields_a_usable_directory():
    """Imports that write no files never commit any, so temp is fine."""
    stage = _make_stage_root()
    assert os.path.isdir(stage)


def test_an_unwritable_root_falls_back_instead_of_raising(tmp_path, monkeypatch):
    """A broken deliverables root is the commit's problem to report, not this."""
    monkeypatch.setattr(
        "app.services.upload_pack.os.makedirs",
        lambda *a, **k: (_ for _ in ()).throw(OSError("read-only")),
    )
    stage = _make_stage_root(str(tmp_path))
    assert os.path.isdir(stage)
