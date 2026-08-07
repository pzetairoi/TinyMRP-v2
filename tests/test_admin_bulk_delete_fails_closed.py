"""Bulk user deletion must fail CLOSED (Phase 8, E2).

The admin-protection guard used to swallow its own exception and fall through
to the deletion:

    try:
        if u.has_role("admin"):
            skipped_admin += 1
            continue
    except Exception:
        pass          # <- execution continued, and u.delete() ran

So a broken role reference or a momentary database error deleted the very
administrator the guard exists to protect. Deletion is irreversible, so "we
could not prove this user is safe to delete" has to mean skip.
"""

from __future__ import annotations

import inspect

from app.views import admin


def _bulk_delete_source() -> str:
    return inspect.getsource(admin.users_bulk_delete)


def test_a_failed_admin_check_skips_rather_than_deletes():
    source = _bulk_delete_source()
    admin_guard = source.split("has_role", 1)[1].split("_cleanup_user_references", 1)[0]

    # The handler for the admin check must end the iteration, not fall through.
    assert "skipped_unverified += 1" in admin_guard
    assert admin_guard.count("continue") >= 2, "both guards must skip on failure"
    # And it must not be silent.
    assert "logger.exception" in admin_guard


def test_no_bare_pass_remains_in_the_delete_loop():
    """A bare pass anywhere in this loop means something failed open again."""
    source = _bulk_delete_source()
    body = source.split("for u in users:", 1)[1]

    for line in body.splitlines():
        assert line.strip() != "pass", f"bare pass reintroduced in the delete loop: {line!r}"


def test_a_failed_deletion_is_counted_and_reported():
    """References are cleaned up BEFORE delete, so a failure leaves damage."""
    source = _bulk_delete_source()

    assert "failed += 1" in source
    assert "Failed to delete" in source
    assert "could not be verified as safe to delete" in source


def test_tools_misc_listing_is_driven_by_the_filesystem(app):
    """E12. The page used to name four files by hand.

    The other eight in static/misc shipped to every install and were reachable
    by nobody, and nothing failed - which is exactly why it went unnoticed for
    so long. Listing the folder means a removed file disappears instead of
    becoming a broken link, and a new one needs no template edit.
    """
    from app.views.tools import _misc_groups

    with app.test_request_context("/"):
        groups = _misc_groups()

    listed = {f["name"] for g in groups for f in g["files"]}
    # The files an engineer actually needs, previously only partly reachable.
    assert "tinymrp_part_customtab.prtprp" in listed
    assert "TinyMRP.swp" in listed, "the macro itself was never linked"
    assert any(n.endswith(".sldbomtbt") for n in listed), "BOM templates were never linked"

    # Branding and icons are not downloads.
    assert not any(n.lower().endswith((".ico", ".png", ".bmp")) for n in listed)
    # Every group carries an explanation; several files are unusable without one.
    assert all(g["description"] for g in groups)


def test_tools_misc_listing_survives_a_missing_folder(app, monkeypatch):
    """A missing folder means nothing to offer, not a 500."""
    from app.views import tools

    monkeypatch.setattr(tools.os, "listdir", lambda _p: (_ for _ in ()).throw(OSError("gone")))
    with app.test_request_context("/"):
        assert tools._misc_groups() == []
