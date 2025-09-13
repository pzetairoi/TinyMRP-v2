from __future__ import annotations
from typing import Iterable, Optional, Set, Tuple

from flask import request, current_app
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
    Phase 2: Admin -> unrestricted; others: union of job BOMs (flattened) where user is participant or supplier user.
    If ACL_ENFORCED is False, return None for backward compatibility.
    """
    try:
        if not getattr(user, "is_authenticated", False):
            return set()
        # Admin always unrestricted
        if "admin" in _role_names(user):
            return None
        # Allow opt-out
        enforce = True
        try:
            enforce = bool(current_app.config.get("ACL_ENFORCED", True))
        except Exception:
            enforce = True
        if not enforce:
            return None

        # Gather jobs where user participates directly
        from app.models.job import Job
        from app.models.supplier import Supplier
        from app.models.customer import Customer
        jobs = list(Job.objects(participants=user))
        # Also jobs where a supplier linked to the user is a vendor
        try:
            supplier_ids = [s.id for s in Supplier.objects(users=user).only("id")]
            if supplier_ids:
                jobs_vendor = Job.objects(vendors__in=supplier_ids)
                jobs.extend([j for j in jobs_vendor if j not in jobs])
        except Exception:
            pass

        # Also jobs for customers linked to the user
        try:
            customer_ids = [c.id for c in Customer.objects(users=user).only("id")]
            if customer_ids:
                jobs_cust = Job.objects(customer__in=customer_ids)
                jobs.extend([j for j in jobs_cust if j not in jobs])
        except Exception:
            pass

        # Flatten BOM for each job top-level line using existing docpacks logic
        from app.services.docpacks import _flatten_bom
        allowed: Set[Tuple[str, str]] = set()
        for j in jobs:
            for line in (j.bom or []):
                try:
                    flat = _flatten_bom(line.pn, line.rev or "", full=True, include_consumed=True)
                    for pn, rev, _ in flat:
                        allowed.add((pn, (rev or "")))
                    # include the root explicitly
                    allowed.add((line.pn, (line.rev or "")))
                except Exception:
                    continue
        return allowed
    except Exception:
        # On failure be conservative: deny all rather than allow all
        return set()


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


def permissions_required(*perms: str):
    """Decorator to enforce any number of permission strings.
    The user must have all specified permissions via any of their roles.
    """
    from functools import wraps
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not getattr(current_user, "is_authenticated", False):
                from flask import abort
                return abort(401)
            # Admin bypass
            try:
                names = _role_names(current_user)
                if "admin" in names:
                    return fn(*args, **kwargs)
            except Exception:
                pass
            for p in perms:
                if not user_has_permission(current_user, p):
                    from flask import abort
                    return abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return deco
