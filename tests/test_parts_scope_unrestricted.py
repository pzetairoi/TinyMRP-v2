"""The BOM authorisation fast path must only fire when it is genuinely free.

Browsing a large assembly made the server appear to hang. The cause was
_bom_is_fully_authorised walking every descendant on every flat-BOM request:
measured at 1801 ms for a 1347-part tree, 10 levels deep. For a user whose
scope filters nothing that walk cannot fail - it was real work answering a
question that was never in doubt.

Skipping an authorisation check is only safe if it could not have said no, so
these tests are about when the shortcut must NOT apply.
"""

from __future__ import annotations

from app.services.authorization import parts_scope_is_unrestricted


class _User:
    is_authenticated = True

    def __init__(self, perms=(), legacy=False):
        self._perms = set(perms)
        self.legacy_admin = legacy


def test_anonymous_never_takes_the_shortcut():
    class _Anon:
        is_authenticated = False

    assert parts_scope_is_unrestricted(_Anon()) is False


def test_without_unreleased_access_the_shortcut_is_refused(monkeypatch):
    """An approved-only filter still hides parts, so the walk must happen."""
    monkeypatch.setattr(
        "app.services.authorization.has_permission",
        lambda user, perm: perm != "parts.read_unreleased",
    )
    monkeypatch.setattr("app.services.authorization._uses_legacy_admin_bypass", lambda u: False)
    assert parts_scope_is_unrestricted(_User()) is False


def test_a_relationship_scoped_user_is_refused(monkeypatch):
    """Not global means parts are filtered by relationship - it can say no."""
    monkeypatch.setattr("app.services.authorization.has_permission", lambda user, perm: True)
    monkeypatch.setattr("app.services.authorization._uses_legacy_admin_bypass", lambda u: False)
    monkeypatch.setattr(
        "app.services.authorization._scope_modes", lambda *a, **k: frozenset({"customer"})
    )
    assert parts_scope_is_unrestricted(_User()) is False


def test_a_global_user_with_unreleased_access_takes_it(monkeypatch):
    monkeypatch.setattr("app.services.authorization.has_permission", lambda user, perm: True)
    monkeypatch.setattr("app.services.authorization._uses_legacy_admin_bypass", lambda u: False)
    monkeypatch.setattr(
        "app.services.authorization._scope_modes", lambda *a, **k: frozenset({"global"})
    )
    assert parts_scope_is_unrestricted(_User()) is True


def test_anything_unexpected_falls_back_to_the_full_walk(monkeypatch):
    """A wrong True skips a real check, so errors must answer False."""
    monkeypatch.setattr("app.services.authorization.has_permission", lambda user, perm: True)
    monkeypatch.setattr("app.services.authorization._uses_legacy_admin_bypass", lambda u: False)

    def _boom(*a, **k):
        raise RuntimeError("scope evaluation failed")

    monkeypatch.setattr("app.services.authorization._scope_context", _boom)
    assert parts_scope_is_unrestricted(_User()) is False
