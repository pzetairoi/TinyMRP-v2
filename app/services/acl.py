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


def is_privileged_internal(user) -> bool:
    roles = _role_names(user)
    return bool({"admin", "operator", "planner"} & roles)


def customer_scope_ids(user) -> list:
    from app.models.customer import Customer
    try:
        return [c.id for c in Customer.objects(users=user).only("id")]
    except Exception:
        return []


def supplier_scope_ids(user) -> list:
    from app.models.supplier import Supplier
    try:
        return [s.id for s in Supplier.objects(users=user).only("id")]
    except Exception:
        return []


def is_external_scoped_user(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if is_privileged_internal(user):
        return False
    roles = _role_names(user)
    cust_ids = customer_scope_ids(user)
    supp_ids = supplier_scope_ids(user)
    if "customer_viewer" in roles or "supplier_viewer" in roles:
        return True
    if "viewer" in roles and (cust_ids or supp_ids):
        return True
    if cust_ids or supp_ids:
        return True
    return False


def _acl_enforced() -> bool:
    try:
        return bool(current_app.config.get("ACL_ENFORCED", True))
    except Exception:
        return True


def apply_job_scope(qs, user):
    if not _acl_enforced():
        return qs
    if not is_external_scoped_user(user):
        return qs
    cust_ids = customer_scope_ids(user)
    supp_ids = supplier_scope_ids(user)
    if not cust_ids and not supp_ids:
        return qs.filter(id__in=[])
    if supp_ids and not cust_ids:
        return qs.filter(id__in=[])

    from mongoengine.queryset.visitor import Q
    from app.models.order import Order

    q = Q()
    if cust_ids:
        q = q | Q(customer__in=cust_ids)
    if supp_ids:
        q = q | Q(vendors__in=supp_ids)
        job_ids = []
        for o in Order.objects(supplier__in=supp_ids).only("job"):
            try:
                if o.job:
                    job_ids.append(o.job.id)
            except Exception:
                continue
        if job_ids:
            q = q | Q(id__in=list(set(job_ids)))
    return qs.filter(q)


def apply_order_scope(qs, user):
    if not _acl_enforced():
        return qs
    if not is_external_scoped_user(user):
        return qs
    cust_ids = customer_scope_ids(user)
    supp_ids = supplier_scope_ids(user)
    if not cust_ids and not supp_ids:
        return qs.filter(id__in=[])

    from mongoengine.queryset.visitor import Q
    from app.models.job import Job

    q = Q()
    if supp_ids:
        q = q | Q(supplier__in=supp_ids)
    if cust_ids:
        q = q | Q(customer__in=cust_ids)
        job_ids = [j.id for j in Job.objects(customer__in=cust_ids).only("id")]
        if job_ids:
            q = q | Q(job__in=job_ids)
    return qs.filter(q)


def apply_customer_scope(qs, user):
    if not _acl_enforced():
        return qs
    if not is_external_scoped_user(user):
        return qs
    cust_ids = customer_scope_ids(user)
    if not cust_ids:
        return qs.filter(id__in=[])
    return qs.filter(id__in=cust_ids)


def apply_supplier_scope(qs, user):
    if not _acl_enforced():
        return qs
    if not is_external_scoped_user(user):
        return qs
    supp_ids = supplier_scope_ids(user)
    if not supp_ids:
        return qs.filter(id__in=[])
    return qs.filter(id__in=supp_ids)


def can_access_customer(user, customer) -> bool:
    if not _acl_enforced():
        return True
    if not is_external_scoped_user(user):
        return True
    cust_ids = customer_scope_ids(user)
    try:
        return bool(customer and customer.id in cust_ids)
    except Exception:
        return False


def can_access_supplier(user, supplier) -> bool:
    if not _acl_enforced():
        return True
    if not is_external_scoped_user(user):
        return True
    supp_ids = supplier_scope_ids(user)
    try:
        return bool(supplier and supplier.id in supp_ids)
    except Exception:
        return False


def can_access_job(user, job) -> bool:
    if not _acl_enforced():
        return True
    if not is_external_scoped_user(user):
        return True
    cust_ids = customer_scope_ids(user)
    supp_ids = supplier_scope_ids(user)
    if supp_ids and not cust_ids:
        return False
    try:
        if cust_ids and getattr(job, "customer", None) and job.customer.id in cust_ids:
            return True
    except Exception:
        pass
    try:
        if supp_ids and getattr(job, "vendors", None):
            if any(v.id in supp_ids for v in (job.vendors or [])):
                return True
    except Exception:
        pass
    if supp_ids:
        try:
            from app.models.order import Order
            if Order.objects(supplier__in=supp_ids, job=job).limit(1).count() > 0:
                return True
        except Exception:
            pass
    return False


def can_access_order(user, order) -> bool:
    if not _acl_enforced():
        return True
    if not is_external_scoped_user(user):
        return True
    cust_ids = customer_scope_ids(user)
    supp_ids = supplier_scope_ids(user)
    try:
        if supp_ids and getattr(order, "supplier", None) and order.supplier.id in supp_ids:
            return True
    except Exception:
        pass
    try:
        if cust_ids and getattr(order, "customer", None) and order.customer.id in cust_ids:
            return True
    except Exception:
        pass
    try:
        if cust_ids and getattr(order, "job", None) and order.job and order.job.customer and order.job.customer.id in cust_ids:
            return True
    except Exception:
        pass
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
        # Admin/operator/planner always unrestricted
        if is_privileged_internal(user):
            return None
        # Allow opt-out
        if not _acl_enforced():
            return None
        if not is_external_scoped_user(user):
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
        customer_ids = [c.id for c in Customer.objects(users=user).only("id")]
        supplier_ids = [s.id for s in Supplier.objects(users=user).only("id")]
        if customer_ids:
            for j in Job.objects(customer__in=customer_ids):
                for line in (j.bom or []):
                    add_with_children(line.pn or "", line.rev or "")
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
