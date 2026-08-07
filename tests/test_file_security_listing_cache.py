"""The thumbnail lookup cache must not become a security hole.

Measured on a live instance: resolving one thumbnail per file record cost
524 ms of a 705 ms parts-list response, because each resolution stats the
filesystem several times. A per-request directory listing collapses that.

These tests exist for one reason: a cache that answers "does this file exist"
must never start answering "is this file allowed". Containment is still proved
by _validate_candidate, and that must stay true.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.file_security import (
    FileSecurityError,
    _candidate_file_exists,
    _dir_file_names,
    _validate_candidate,
)


def test_listing_cache_is_disabled_outside_a_request(tmp_path):
    """No request, no cache - a CLI or worker must never hold a stale listing."""
    assert _dir_file_names(tmp_path) is None

    real = tmp_path / "thumb.png"
    real.write_bytes(b"x")
    # Falls back to touching the filesystem, so it still answers correctly.
    assert _candidate_file_exists(real) is True
    assert _candidate_file_exists(tmp_path / "missing.png") is False


def test_cache_survives_only_within_one_request(app, tmp_path):
    """A file added between requests must be visible to the next one."""
    with app.test_request_context("/"):
        assert _candidate_file_exists(tmp_path / "late.png") is False
        (tmp_path / "late.png").write_bytes(b"x")
        # Same request: the listing is deliberately still the old one.
        assert _candidate_file_exists(tmp_path / "late.png") is False

    with app.test_request_context("/"):
        assert _candidate_file_exists(tmp_path / "late.png") is True


def test_a_directory_is_not_reported_as_a_file(app, tmp_path):
    (tmp_path / "subdir").mkdir()
    with app.test_request_context("/"):
        assert _candidate_file_exists(tmp_path / "subdir") is False


def test_containment_is_still_enforced_and_not_served_from_the_cache(app, tmp_path):
    """The cache accelerates existence. It must never authorise an escape.

    A file that genuinely EXISTS outside the approved root must still be
    rejected - existence and permission are different questions.
    """
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"x")

    with app.test_request_context("/"):
        # It exists...
        assert _candidate_file_exists(outside) is True
        # ...and is still refused, because it is not inside the root.
        with pytest.raises(FileSecurityError):
            _validate_candidate(outside, root, must_exist=True)


def test_traversal_out_of_the_root_is_still_refused(app, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "escape.png"
    target.write_bytes(b"x")

    with app.test_request_context("/"):
        with pytest.raises(FileSecurityError):
            _validate_candidate(Path(str(root / ".." / "escape.png")), root, must_exist=True)
