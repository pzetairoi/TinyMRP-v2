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
    """Compatibility wrapper around the central Stage 2 evaluator."""

    from app.services.authorization import has_permission

    return has_permission(user, perm)


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

def participant_job_ids(user) -> list:
    from app.models.job import Job
    try:
        return [j.id for j in Job.objects(participants=user, is_deleted=False).only("id")]
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
    job_ids = participant_job_ids(user)
    if "customer_viewer" in roles or "supplier_viewer" in roles:
        return True
    if "viewer" in roles and (cust_ids or supp_ids or job_ids):
        return True
    if cust_ids or supp_ids or job_ids:
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
    from app.services.authorization import scope_queryset

    return scope_queryset(qs, user, "jobs")


def apply_order_scope(qs, user):
    if not _acl_enforced():
        return qs
    from app.services.authorization import scope_queryset

    return scope_queryset(qs, user, "orders")


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
    job_ids = participant_job_ids(user)
    try:
        if job_ids and job and job.id in job_ids:
            return True
    except Exception:
        pass
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
    job_ids = participant_job_ids(user)
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
    try:
        if job_ids and getattr(order, "job", None) and order.job and order.job.id in job_ids:
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
        from app.services.authorization import has_permission, permission_scope_modes

        modes = permission_scope_modes(
            user,
            "parts.read",
            resource_type="parts",
        )
        if "global" in modes:
            return None
        if not is_external_scoped_user(user):
            return None

        from app.models.bom import BOMLink
        from app.models.customer import Customer
        from app.models.part import Part
        from app.models.supplier import Supplier
        from app.models.job import Job
        from app.models.order import Order

        def resolve_revision(pn: str, rev: str) -> str:
            rev_clean = str(rev or "").strip()
            if rev_clean:
                return rev_clean
            parts = Part.objects(part_number__iexact=str(pn or "").strip())
            if not has_permission(user, "parts.read_unreleased"):
                from app.services.attrs import approval_filter_raw

                parts = parts.filter(__raw__=approval_filter_raw(approved=True))
            part = parts.only("revision", "updated_at").order_by("-updated_at").first()
            return str(getattr(part, "revision", "") or "").strip() if part else ""

        def add_with_children(pn: str, rev: str):
            pn_clean = (pn or "").strip()
            if not pn_clean:
                return
            root = (pn_clean, resolve_revision(pn_clean, rev))
            queue = [root]
            visited: Set[Tuple[str, str]] = set()
            while queue:
                current_pn, current_rev = queue.pop()
                current_rev = resolve_revision(current_pn, current_rev)
                key = (current_pn, current_rev)
                if key in visited:
                    continue
                visited.add(key)
                allowed.add(key)
                links = BOMLink.objects(parent_pn__iexact=current_pn).only(
                    "parent_rev",
                    "child_pn",
                    "child_rev",
                )
                for link in links:
                    link_parent_rev = str(
                        getattr(link, "parent_rev", "") or ""
                    ).strip()
                    if (
                        resolve_revision(current_pn, link_parent_rev).casefold()
                        != current_rev.casefold()
                    ):
                        continue
                    child_pn = str(getattr(link, "child_pn", "") or "").strip()
                    if not child_pn:
                        continue
                    queue.append(
                        (
                            child_pn,
                            resolve_revision(
                                child_pn,
                                str(
                                    getattr(link, "child_rev", "") or ""
                                ).strip(),
                            ),
                        )
                    )

        allowed: Set[Tuple[str, str]] = set()
        customer_ids = [c.id for c in Customer.objects(users=user).only("id")]
        supplier_ids = [s.id for s in Supplier.objects(users=user).only("id")]
        assigned_job_ids = set(participant_job_ids(user))
        customer_job_ids = set()
        if customer_ids:
            customer_job_ids.update(
                j.id
                for j in Job.objects(
                    customer__in=customer_ids,
                    is_deleted=False,
                ).only("id")
            )
        supplier_job_ids = set()
        if supplier_ids:
            supplier_job_ids.update(
                j.id
                for j in Job.objects(
                    vendors__in=supplier_ids,
                    is_deleted=False,
                ).only("id")
            )
            supplier_job_ids.update(
                order.job.id
                for order in Order.objects(
                    kind="purchase",
                    supplier__in=supplier_ids,
                ).only("job")
                if getattr(order, "job", None)
            )

        job_ids = assigned_job_ids | customer_job_ids | supplier_job_ids
        if job_ids:
            for j in Job.objects(id__in=list(job_ids), is_deleted=False):
                for line in (j.bom or []):
                    add_with_children(line.pn or "", line.rev or "")

        if customer_ids:
            from mongoengine.queryset.visitor import Q

            customer_orders = Order.objects(
                Q(kind="sales", customer__in=customer_ids)
                | Q(kind="sales", job__in=list(customer_job_ids))
            )
            for o in customer_orders:
                for line in (o.lines or []):
                    add_with_children(line.pn or "", line.rev or "")

        if assigned_job_ids:
            for o in Order.objects(job__in=list(assigned_job_ids)):
                for line in (o.lines or []):
                    add_with_children(line.pn or "", line.rev or "")

        if supplier_ids:
            for o in Order.objects(
                kind="purchase",
                supplier__in=supplier_ids,
            ):
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
            from app.services.authorization import authorise

            for p in perms:
                if not authorise(current_user, p).allowed:
                    from flask import abort
                    return abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return deco
