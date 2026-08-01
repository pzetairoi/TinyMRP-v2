# app/services/impersonation.py — swap into a seeded permission-test user.
"""Let an administrator act as a permission-test account without re-logging in.

Every guard lives here rather than in the view or template, so the dropdown is
purely cosmetic and cannot widen what the endpoint accepts. Four conditions must
all hold, checked on the request that performs the swap:

* ``ALLOW_PERMISSION_TEST_DATA`` is enabled for the instance,
* the actor holds the same permissions the permission-test seed already needs,
* the target matches the exact seeded ``permtest.*`` pattern on the configured
  domain, and
* the target is not an administrator.

The original identity is kept in the session purely so the swap can be undone
and audited; permission checks only ever see the impersonated user, so the
legacy admin bypass cannot leak into a test session.
"""
from __future__ import annotations

import re
from typing import Any

from flask import current_app, session

from app.models.auth import User

# Session keys. ``_REAL`` is the administrator who started the swap.
_REAL = "_impersonator_id"

# The permissions already required to seed the permission-test environment.
REQUIRED_PERMISSIONS = ("security.users.manage", "security.assignments.manage")

_ADMIN_ROLES = {"administrator", "security_administrator"}


def _domain() -> str:
    from app.services.rls_demo import _normalize_domain

    return _normalize_domain(
        str(current_app.config.get("PERMISSION_TEST_DATA_DOMAIN") or "demo.com")
    )


def enabled() -> bool:
    """Whether this instance exposes impersonation at all."""
    return bool(current_app.config.get("ALLOW_PERMISSION_TEST_DATA", False))


def _is_admin(user: Any) -> bool:
    try:
        return any(
            str(getattr(role, "name", "")).strip().casefold() in _ADMIN_ROLES
            for role in (getattr(user, "roles", None) or [])
        )
    except Exception:
        return True  # fail closed: an unreadable role set is treated as admin


def is_permission_test_user(user: Any) -> bool:
    """Exactly the seeded ``permtest.<scenario>@<domain>`` accounts."""
    email = str(getattr(user, "email", "") or "").strip().lower()
    if not email:
        return False
    pattern = rf"^permtest\.[a-z0-9_]+@{re.escape(_domain())}$"
    return bool(re.match(pattern, email)) and not _is_admin(user)


def may_impersonate(actor: Any) -> bool:
    """Whether ``actor`` may start a swap on this instance."""
    from app.services.authorization import has_permission

    if not enabled() or not getattr(actor, "is_authenticated", False):
        return False
    # Never allow chaining: an already-impersonated session cannot swap again.
    if impersonator_id():
        return False
    return all(has_permission(actor, name) for name in REQUIRED_PERMISSIONS)


def available_targets(actor: Any) -> list[User]:
    """Seeded test users the actor may become, or an empty list."""
    if not may_impersonate(actor):
        return []
    pattern = rf"^permtest\.[a-z0-9_]+@{re.escape(_domain())}$"
    targets = [
        user
        for user in User.objects(email__regex=pattern)
        if is_permission_test_user(user) and getattr(user, "active", False)
    ]
    return sorted(targets, key=lambda user: str(user.email or ""))


def resolve_target(actor: Any, email: str) -> User | None:
    """The requested target, only if every guard passes."""
    wanted = str(email or "").strip().lower()
    if not wanted:
        return None
    return next(
        (user for user in available_targets(actor) if str(user.email or "").lower() == wanted),
        None,
    )


def impersonator_id() -> str:
    """Identifier of the administrator behind the current session, if any."""
    return str(session.get(_REAL) or "")


def begin(actor: Any) -> None:
    """Record who started the swap so it can be undone and attributed."""
    session[_REAL] = str(getattr(actor, "id", "") or "")


def end() -> str:
    """Clear the marker, returning the administrator's identifier."""
    return str(session.pop(_REAL, "") or "")


def real_user() -> User | None:
    """The administrator behind an impersonated session, for audit context."""
    identifier = impersonator_id()
    if not identifier:
        return None
    try:
        return User.objects(id=identifier).first()
    except Exception:
        return None
