from __future__ import annotations
from typing import Iterable, Optional, Set, Tuple

from flask import request
from flask_login import current_user


def _role_names(user) -> Set[str]:
    names: Set[str] = set()
    try:
        for r in (user.roles or []):
            n = getattr(r, "name", None)
            if n: names.add(str(n))
    except Exception:
        pass
    return names


def user_has_permission(user, perm: str) -> bool:
    """Check if the user has a given permission string via any of their roles."""
    try:
        for r in (user.roles or []):
            perms = getattr(r, "permissions", []) or []
            if perm in perms:
                return True
    except Exception:
        return False
    return False


def user_can_view_items(user) -> bool:
    # Any of these permissions qualifies for read access to items
    for p in ("items.view", "bom.view", "reports.view"):
        if user_has_permission(user, p):
            return True
    # Admin role shortcut
    if "admin" in _role_names(user):
        return True
    return False


def allowed_parts_for(user) -> Optional[Set[Tuple[str, str]]]:
    """Return a set of (pn,rev) pairs the user can access, or None for unrestricted.
    Phase 1 placeholder: unrestricted for users with items.view or admin; otherwise empty set.
    """
    if not user.is_authenticated:
        return set()
    if user_can_view_items(user):
        return None  # unrestricted for now
    return set()  # no access


def require_items_view(fn):
    """Decorator to enforce that current_user can view items.
    Use alongside @login_required.
    """
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not getattr(current_user, "is_authenticated", False):
            from flask import abort
            return abort(401)
        if not user_can_view_items(current_user):
            from flask import abort
            return abort(403)
        return fn(*args, **kwargs)
    return wrapper

