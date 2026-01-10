from __future__ import annotations
from typing import Optional, Set, Tuple

from flask import current_app
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


def part_is_allowed(allowed: Optional[Set[Tuple[str, str]]], pn: str, rev: str | None) -> bool:
    if allowed is None:
        return True
    if not allowed:
        return False
    pn_key = (pn or "").strip()
    rev_key = (rev or "").strip()
    if (pn_key, rev_key) in allowed:
        return True
    pn_l = pn_key.lower()
    rev_l = rev_key.lower()
    for apn, arev in allowed:
        apn_l = (apn or "").strip().lower()
        if apn_l != pn_l:
            continue
        if not arev:
            return True
        if (arev or "").strip().lower() == rev_l:
            return True
    return False


def allowed_parts_for(user) -> Optional[Set[Tuple[str, str]]]:
    """Return a set of (pn,rev) pairs the user can access, or None for unrestricted.
    Admin -> unrestricted. Customer/supplier viewers: restrict to their jobs/orders (plus BOM children).
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

        roles = _role_names(user)
        is_customer_viewer = "customer_viewer" in roles
        is_supplier_viewer = "supplier_viewer" in roles
        if not (is_customer_viewer or is_supplier_viewer):
            return None

        from app.models.part import Part
        from app.services.attrs import harvest_part_attrs
        from app.services.docpacks import _flatten_bom
        from app.models.customer import Customer
        from app.models.supplier import Supplier
        from app.models.job import Job
        from app.models.order import Order

        def resolve_rev(pn: str, rev: str) -> str:
            rev = (rev or "").strip()
            if rev:
                return rev
            p = Part.objects(part_number__iexact=pn).order_by("-updated_at").first()
            if not p:
                return ""
            attrs = harvest_part_attrs(p)
            return (attrs.get("revision") or p.revision or "").strip()

        def add_with_children(pn: str, rev: str):
            pn_clean = (pn or "").strip()
            if not pn_clean:
                return
            rev_clean = resolve_rev(pn_clean, rev)
            allowed.add((pn_clean, rev_clean))
            if not rev:
                allowed.add((pn_clean, ""))  # wildcard for unknown rev
            try:
                flat = _flatten_bom(pn_clean, rev_clean, full=True, include_consumed=True)
                for cpn, crev, _ in flat:
                    allowed.add((cpn, (crev or "")))
            except Exception:
                pass

        allowed: Set[Tuple[str, str]] = set()
        if is_customer_viewer:
            customer_ids = [c.id for c in Customer.objects(users=user).only("id")]
            if customer_ids:
                for j in Job.objects(customer__in=customer_ids):
                    for line in (j.bom or []):
                        add_with_children(line.pn or "", line.rev or "")

        if is_supplier_viewer:
            supplier_ids = [s.id for s in Supplier.objects(users=user).only("id")]
            if supplier_ids:
                for o in Order.objects(supplier__in=supplier_ids):
                    for line in (o.lines or []):
                        add_with_children(line.pn or "", line.rev or "")

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
