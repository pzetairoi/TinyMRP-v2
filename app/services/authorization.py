"""Small, fail-closed backend authorisation primitives.

This module supplies the Stage 2 API without migrating route-level object
lookups or serializers. It contains no policy language and no process-wide
cache of users, roles, or permissions.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import wraps
import re
from typing import Any

from flask import (
    abort,
    current_app,
    g,
    has_app_context,
    has_request_context,
    request,
)
from flask_login import current_user

from app.services.permissions import (
    PERMISSION_REGISTRY,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason_code: str
    permission: str
    resource_type: str = ""
    resource_id: str = ""
    used_legacy_admin_bypass: bool = False


@dataclass(frozen=True)
class _PermissionSnapshot:
    permissions: frozenset[str]
    role_names: frozenset[str]
    role_permissions: tuple[tuple[str, frozenset[str]], ...] = ()


@dataclass(frozen=True)
class _ScopeContext:
    valid: bool
    customer_ids: tuple[Any, ...] = ()
    supplier_ids: tuple[Any, ...] = ()
    participant_job_ids: tuple[Any, ...] = ()
    role_permissions: tuple[tuple[str, frozenset[str]], ...] = ()


class AuthorizationScopeError(RuntimeError):
    """Raised when a scope policy does not exist for a resource type."""


_EMPTY_SNAPSHOT = _PermissionSnapshot(frozenset(), frozenset(), ())
_RESOURCE_PERMISSIONS = {
    "parts": "parts.read",
    "jobs": "jobs.read",
    "orders": "orders.read",
    "customers": "customers.read",
    "suppliers": "suppliers.read",
}
_RESOURCE_ALIASES = {
    "part": "parts",
    "job": "jobs",
    "order": "orders",
    "customer": "customers",
    "supplier": "suppliers",
}

def _is_authenticated(user: Any) -> bool:
    return bool(user is not None and getattr(user, "is_authenticated", False))


def _cache_key(user: Any) -> str:
    user_id = getattr(user, "id", None)
    if user_id is not None:
        return f"id:{user_id}"
    return f"object:{id(user)}"


def _request_cache(name: str) -> dict[str, Any] | None:
    if not has_request_context():
        return None
    cache_name = f"_tinymrp_authorization_{name}"
    cache = getattr(g, cache_name, None)
    if cache is None:
        cache = {}
        setattr(g, cache_name, cache)
    return cache


def _build_permission_snapshot(user: Any) -> _PermissionSnapshot:
    if not _is_authenticated(user):
        return _EMPTY_SNAPSHOT

    direct: set[str] = set()
    role_names: set[str] = set()
    role_permissions: list[tuple[str, frozenset[str]]] = []
    for role in tuple(getattr(user, "roles", None) or ()):
        if role is None or getattr(role, "active", True) is False:
            continue
        name = getattr(role, "name", None)
        permissions = getattr(role, "permissions", None) or ()
        if isinstance(permissions, (str, bytes)):
            continue
        valid = {
            permission
            for permission in permissions
            if isinstance(permission, str) and permission in PERMISSION_REGISTRY
        }
        direct.update(valid)
        if isinstance(name, str) and name:
            role_names.add(name)
            role_permissions.append((name, frozenset(valid)))

    return _PermissionSnapshot(
        permissions=frozenset(direct),
        role_names=frozenset(role_names),
        role_permissions=tuple(role_permissions),
    )


def _permission_snapshot(user: Any) -> _PermissionSnapshot:
    cache = _request_cache("permission_snapshots")
    key = _cache_key(user)
    if cache is not None and key in cache:
        return cache[key]
    snapshot = _build_permission_snapshot(user)
    if cache is not None:
        cache[key] = snapshot
    return snapshot


def effective_permissions(user: Any) -> frozenset[str]:
    """Return the immutable union of all valid permissions assigned to a user."""

    try:
        return _permission_snapshot(user).permissions
    except Exception:
        return frozenset()


def legacy_admin_bypass_enabled() -> bool:
    """Whether holding a role literally named ``admin`` still bypasses RBAC.

    DEFAULT FLIPPED TO OFF 2026-08-09 (productionmaturityplan A3). This was the
    single widest hole in the permission system: one role name granted every
    permission in the registry without consulting the registry at all.

    Checked against the live fleet before flipping, because a role name lives
    in databases and not only in code:
      mecs (production)  0 users held it. Everyone is administrator,
                         engineering or customer.
      test               1 user, migrated additively to administrator first.

    Still overridable, so an instance that discovers a dependency can set
    LEGACY_ADMIN_BYPASS_ENABLED=1 to restore the old behaviour while it
    reassigns roles properly. That escape hatch is the reason this is a
    default change rather than a deletion.
    """

    return (
        bool(current_app.config.get("LEGACY_ADMIN_BYPASS_ENABLED", False))
        if has_app_context()
        else False
    )


def _uses_legacy_admin_bypass(user: Any) -> bool:
    if not _is_authenticated(user) or not legacy_admin_bypass_enabled():
        return False
    return "admin" in _permission_snapshot(user).role_names


def has_permission(user: Any, permission: str) -> bool:
    """Return whether a registered permission is effective for the user."""

    if (
        not isinstance(permission, str)
        or permission not in PERMISSION_REGISTRY
        or not _is_authenticated(user)
    ):
        return False
    try:
        return _uses_legacy_admin_bypass(user) or permission in effective_permissions(
            user
        )
    except Exception:
        return False


def has_any_permission(user: Any, permissions: Iterable[str]) -> bool:
    return any(has_permission(user, permission) for permission in permissions)


def _resource_identity(
    resource: Any,
    context: Mapping[str, Any] | None,
) -> tuple[str, str]:
    resource_type = str((context or {}).get("resource_type") or "")
    resource_id = str((context or {}).get("resource_id") or "")
    if resource is not None:
        resource_type = resource_type or type(resource).__name__.lower()
        resource_id = resource_id or str(getattr(resource, "id", "") or "")
    return resource_type, resource_id


def _denied(
    user: Any,
    *,
    reason_code: str,
    permission: str,
    resource_type: str = "",
    resource_id: str = "",
    used_legacy_admin_bypass: bool = False,
) -> AuthorizationDecision:
    decision = AuthorizationDecision(
        False, reason_code, permission, resource_type, resource_id,
        used_legacy_admin_bypass,
    )
    try:
        log_authorization_denial(user, decision)
    except Exception:
        # A denial nobody recorded is an access-control decision with no audit
        # trail. The denial itself still stands; only the record was lost.
        logger.exception("failed to record authorization denial for %s", permission)
    return decision


def authorise(
    user: Any,
    permission: str,
    *,
    resource: Any = None,
    context: Mapping[str, Any] | None = None,
) -> AuthorizationDecision:
    resource_type, resource_id = _resource_identity(resource, context)
    if not isinstance(permission, str) or permission not in PERMISSION_REGISTRY:
        reason = "invalid_permission"
        permission = str(permission or "")
    elif not _is_authenticated(user):
        reason = "unauthenticated"
    else:
        reason = ""
    try:
        snapshot = _permission_snapshot(user) if not reason else _EMPTY_SNAPSHOT
        used_admin = not reason and _uses_legacy_admin_bypass(user)
        if not reason and not used_admin and permission not in snapshot.permissions:
            reason = "missing_permission"
    except Exception:
        reason, used_admin = "authorisation_error", False
    if reason:
        return _denied(
            user,
            reason_code=reason,
            permission=permission,
            resource_type=resource_type,
            resource_id=resource_id,
        )
    return AuthorizationDecision(
        True, "allowed", permission, resource_type, resource_id, used_admin,
    )


def log_authorization_denial(user: Any, decision: AuthorizationDecision) -> None:
    """Best-effort structured denial audit; logging failure never grants access."""

    if decision.allowed:
        return
    endpoint = str(request.endpoint or request.path or "") if has_request_context() else ""
    method = str(request.method or "") if has_request_context() else ""
    actor_id = str(getattr(user, "id", "") or "") if user is not None else ""
    fingerprint = str((
        actor_id, decision.permission, decision.resource_type,
        decision.resource_id, decision.reason_code, endpoint, method,
    ))
    cache = _request_cache("denial_events")
    if cache is not None and fingerprint in cache:
        return
    if cache is not None:
        cache[fingerprint] = True
    from app.services.audit import log_action

    log_action(
        "authorization.denied",
        resource_type=decision.resource_type or "authorization",
        resource=decision.resource_id,
        meta={
            "actor_id": actor_id, "permission": decision.permission,
            "reason_code": decision.reason_code, "endpoint": endpoint,
            "method": method,
            "used_legacy_admin_bypass": decision.used_legacy_admin_bypass,
        },
    )


def _build_scope_context(user: Any) -> _ScopeContext:
    if not _is_authenticated(user):
        return _ScopeContext(valid=False)
    try:
        snapshot = _permission_snapshot(user)
        # Superseded slugs stay listed so users still holding one remain
        # scoped instead of falling through to global visibility.
        scoped_roles = {
            "customer", "supplier",
            "customer_portal", "customer_viewer", "supplier_portal",
            "supplier_viewer", "production_operator", "operator", "viewer",
        }
        if not snapshot.role_names & scoped_roles:
            return _ScopeContext(True, role_permissions=snapshot.role_permissions)
        from app.models.customer import Customer
        from app.models.job import Job
        from app.models.supplier import Supplier

        customer_ids = tuple(Customer.objects(users=user).distinct("id"))
        supplier_ids = tuple(Supplier.objects(users=user).distinct("id"))
        participant_ids = tuple(
            Job.objects(participants=user, is_deleted=False).distinct("id")
        )
        return _ScopeContext(
            True,
            customer_ids=customer_ids,
            supplier_ids=supplier_ids,
            participant_job_ids=participant_ids,
            role_permissions=snapshot.role_permissions,
        )
    except Exception:
        return _ScopeContext(valid=False)


def _scope_context(user: Any) -> _ScopeContext:
    cache = _request_cache("scope_contexts")
    key = _cache_key(user)
    if cache is not None and key in cache:
        return cache[key]
    scope = _build_scope_context(user)
    if cache is not None:
        cache[key] = scope
    return scope


def _normalise_resource_type(resource_type: str) -> str:
    value = str(resource_type or "").strip().lower()
    return _RESOURCE_ALIASES.get(value, value)


def _deny_all(queryset: Any) -> Any:
    return queryset.filter(id__in=[])


def _scope_modes(
    scope: _ScopeContext,
    resource_type: str,
    permission: str,
) -> frozenset[str]:
    """Return the union of scope contributions from roles granting permission."""

    modes: set[str] = set()
    # Any role absent from this map contributes "global" below, so every
    # deliberately scoped standard role must appear here. Superseded slugs stay
    # listed so users still holding one remain scoped.
    fixed = {
        "customer": "customer", "supplier": "supplier",
        "customer_portal": "customer", "customer_viewer": "customer",
        "supplier_portal": "supplier", "supplier_viewer": "supplier",
        "production_operator": "assigned", "operator": "assigned",
    }
    for role_name, permissions in scope.role_permissions:
        if permission not in permissions:
            continue
        if role_name in fixed:
            modes.add(fixed[role_name])
            continue
        if role_name == "viewer" and (
            scope.customer_ids or scope.supplier_ids or scope.participant_job_ids
        ):
            if scope.customer_ids:
                modes.add("customer")
            if scope.supplier_ids:
                modes.add("supplier")
            if scope.participant_job_ids:
                modes.add("assigned")
            continue
        business_mode = {
            ("orders", "procurement"): "purchase",
            ("orders", "sales_customer_service"): "sales",
            ("jobs", "procurement"): "purchasing",
            ("jobs", "sales_customer_service"): "customer_business",
        }.get((resource_type, role_name))
        if business_mode:
            modes.add(business_mode)
            continue
        modes.add("global")
    return frozenset(modes)


def _scope_jobs(queryset: Any, scope: _ScopeContext, modes: frozenset[str]) -> Any:
    from mongoengine.queryset.visitor import Q

    clauses = []
    if "customer" in modes and scope.customer_ids:
        clauses.append(Q(customer__in=scope.customer_ids))
    if "assigned" in modes and scope.participant_job_ids:
        clauses.append(Q(id__in=scope.participant_job_ids))
    if "supplier" in modes and scope.supplier_ids:
        from app.models.order import Order

        clauses.append(Q(vendors__in=scope.supplier_ids))
        order_job_ids = _distinct_ids(
            Order.objects(supplier__in=scope.supplier_ids), "job"
        )
        if order_job_ids:
            clauses.append(Q(id__in=tuple(order_job_ids)))
    if "purchasing" in modes:
        from app.models.order import Order

        purchase_job_ids = _distinct_ids(Order.objects(kind="purchase"), "job")
        clauses.append(Q(vendors__ne=[]))
        if purchase_job_ids:
            clauses.append(Q(id__in=tuple(purchase_job_ids)))
    if "customer_business" in modes:
        clauses.append(Q(customer__ne=None))
    if not clauses:
        return _deny_all(queryset)
    query = clauses[0]
    for clause in clauses[1:]:
        query |= clause
    return queryset.filter(query)


def _scope_orders(queryset: Any, scope: _ScopeContext, modes: frozenset[str]) -> Any:
    from mongoengine.queryset.visitor import Q

    clauses = []
    if "purchase" in modes:
        clauses.append(Q(kind="purchase"))
    if "sales" in modes:
        clauses.append(Q(kind="sales"))
    if "supplier" in modes and scope.supplier_ids:
        clauses.append(Q(kind="purchase", supplier__in=scope.supplier_ids))
    if "customer" in modes and scope.customer_ids:
        clauses.append(Q(kind="sales", customer__in=scope.customer_ids))
        from app.models.job import Job

        customer_job_ids = _distinct_ids(
            Job.objects(customer__in=scope.customer_ids, is_deleted=False),
            "id",
        )
        if customer_job_ids:
            clauses.append(Q(kind="sales", job__in=tuple(customer_job_ids)))
    if "assigned" in modes and scope.participant_job_ids:
        clauses.append(Q(job__in=scope.participant_job_ids))
    if not clauses:
        return _deny_all(queryset)
    query = clauses[0]
    for clause in clauses[1:]:
        query |= clause
    return queryset.filter(query)


def _scope_parts(
    queryset: Any,
    user: Any,
    modes: frozenset[str],
) -> Any:
    from mongoengine.queryset.visitor import Q
    from app.services.attrs import approval_filter_raw

    scoped = queryset
    if "global" not in modes:
        allowed = relationship_part_pairs(user)
        if allowed is None or not allowed:
            return _deny_all(queryset)
        clauses = [
            {
                "part_number": str(pn).strip(),
                "revision": str(rev or "").strip(),
            }
            for pn, rev in allowed
            if str(pn or "").strip()
        ]
        if not clauses:
            return _deny_all(queryset)
        scoped = scoped.filter(Q(__raw__={"$or": clauses}))
    if not has_permission(user, "parts.read_unreleased"):
        scoped = scoped.filter(__raw__=approval_filter_raw(approved=True))
    return scoped


def parts_scope_is_unrestricted(user: Any) -> bool:
    """True when this user's parts scope filters NOTHING.

    _scope_parts narrows a queryset in exactly two ways: a relationship clause
    when the scope is not global, and an approved-only clause when the user
    cannot read unreleased parts. If neither applies, every part is visible and
    any per-part authorisation check can only ever return "allowed".

    That matters because proving authorisation over a whole BOM subtree costs a
    breadth-first walk of every descendant - measured at 1.8 seconds for a
    1347-part assembly - and for an administrator it cannot fail. The work was
    real; the question it answered was not.

    Deliberately conservative: anything unexpected returns False and the caller
    does the full walk. A wrong True would skip a real check.
    """
    try:
        if not _is_authenticated(user):
            return False
        if not has_permission(user, "parts.read_unreleased"):
            return False
        if _uses_legacy_admin_bypass(user):
            return True
        scope = _scope_context(user)
        if not scope.valid:
            return False
        modes = _scope_modes(scope, "parts", _RESOURCE_PERMISSIONS["parts"])
        return "global" in modes
    except Exception:
        return False


def relationship_ids(user: Any, relationship: str) -> tuple[Any, ...]:
    """Return request-cached linked customer or supplier identifiers."""

    scope = _scope_context(user)
    if not scope.valid:
        return ()
    if relationship == "customer":
        return scope.customer_ids
    if relationship == "supplier":
        return scope.supplier_ids
    return ()


def _distinct_ids(queryset: Any, field: str) -> set[Any]:
    return {
        getattr(value, "id", value)
        for value in queryset.distinct(field)
        if value is not None
    }


def relationship_part_pairs(user: Any) -> set[tuple[str, str]] | None:
    """Return exact relationship-derived parts, including recursive BOM children."""

    cache = _request_cache("part_scope_pairs")
    key = _cache_key(user)
    if cache is not None and key in cache:
        return cache[key]

    allowed = _build_relationship_part_pairs(user)
    if cache is not None:
        cache[key] = allowed
    return allowed


def _build_relationship_part_pairs(user: Any) -> set[tuple[str, str]] | None:
    if not _is_authenticated(user):
        return set()
    try:
        if not current_app.config.get("ACL_ENFORCED", True):
            return None
    except Exception:
        pass
    scope = _scope_context(user)
    if not scope.valid:
        return set()
    modes = _scope_modes(scope, "parts", "parts.read")
    if "global" in modes or _uses_legacy_admin_bypass(user):
        return None
    if not (
        scope.customer_ids
        or scope.supplier_ids
        or scope.participant_job_ids
        or modes & {"customer", "supplier", "assigned"}
    ):
        return None

    from mongoengine.queryset.visitor import Q
    from app.models.bom import BOMLink
    from app.models.job import Job
    from app.models.order import Order
    from app.models.part import Part
    from app.services.attrs import approval_filter_raw

    job_ids = set(scope.participant_job_ids)
    customer_jobs: set[Any] = set()
    if scope.customer_ids:
        customer_jobs = _distinct_ids(
            Job.objects(customer__in=scope.customer_ids, is_deleted=False),
            "id",
        )
        job_ids |= customer_jobs
    if scope.supplier_ids:
        job_ids |= _distinct_ids(
            Job.objects(vendors__in=scope.supplier_ids, is_deleted=False),
            "id",
        )
        job_ids |= _distinct_ids(
            Order.objects(kind="purchase", supplier__in=scope.supplier_ids),
            "job",
        )

    roots: set[tuple[str, str]] = set()
    if job_ids:
        for job in Job.objects(id__in=tuple(job_ids), is_deleted=False).only("bom"):
            roots.update(
                (str(line.pn or "").strip(), str(line.rev or "").strip())
                for line in job.bom or ()
                if str(line.pn or "").strip()
            )
    order_query = Q(id__in=[])
    if scope.customer_ids:
        order_query |= Q(kind="sales", customer__in=scope.customer_ids)
        if customer_jobs:
            order_query |= Q(kind="sales", job__in=tuple(customer_jobs))
    if scope.supplier_ids:
        order_query |= Q(kind="purchase", supplier__in=scope.supplier_ids)
    if scope.participant_job_ids:
        order_query |= Q(job__in=scope.participant_job_ids)
    for order in Order.objects(order_query).only("lines"):
        roots.update(
            (str(line.pn or "").strip(), str(line.rev or "").strip())
            for line in order.lines or ()
            if str(line.pn or "").strip()
        )

    revision_cache: dict[str, str] = {}

    def resolve_blank_revisions(part_numbers: set[str]) -> None:
        missing = {pn for pn in part_numbers if pn.casefold() not in revision_cache}
        if not missing:
            return
        parts = Part.objects(part_number__in=tuple(missing))
        if not has_permission(user, "parts.read_unreleased"):
            parts = parts.filter(__raw__=approval_filter_raw(approved=True))
        for part in parts.only("part_number", "revision", "updated_at").order_by("-updated_at"):
            revision_cache.setdefault(
                str(part.part_number or "").strip().casefold(),
                str(part.revision or "").strip(),
            )
        for pn in missing:
            revision_cache.setdefault(pn.casefold(), "")

    allowed: set[tuple[str, str]] = set()
    frontier = roots
    while frontier:
        resolve_blank_revisions({pn for pn, rev in frontier if not rev})
        current = {
            (pn, rev or revision_cache.get(pn.casefold(), ""))
            for pn, rev in frontier
            if pn
        } - allowed
        if not current:
            break
        allowed |= current
        parent_numbers = {pn for pn, _rev in current}
        links = BOMLink.objects(parent_pn__in=tuple(parent_numbers)).only(
            "parent_pn",
            "parent_rev",
            "child_pn",
            "child_rev",
        )
        frontier = set()
        current_folded = {(pn.casefold(), rev.casefold()) for pn, rev in current}
        for link in links:
            parent_pn = str(link.parent_pn or "").strip()
            parent_rev = str(link.parent_rev or "").strip()
            if not parent_rev:
                resolve_blank_revisions({parent_pn})
                parent_rev = revision_cache.get(parent_pn.casefold(), "")
            if (parent_pn.casefold(), parent_rev.casefold()) not in current_folded:
                continue
            child_pn = str(link.child_pn or "").strip()
            if child_pn:
                frontier.add((child_pn, str(link.child_rev or "").strip()))
    return allowed


def scope_queryset(
    queryset: Any,
    user: Any,
    resource_type: str,
    *,
    permission: str | None = None,
) -> Any:
    """Apply a supported resource scope, returning deny-all on evaluation errors."""

    normalized = _normalise_resource_type(resource_type)
    if normalized not in _RESOURCE_PERMISSIONS:
        raise AuthorizationScopeError(f"Unsupported resource type: {resource_type}")
    if not _is_authenticated(user):
        return _deny_all(queryset)
    if _uses_legacy_admin_bypass(user):
        return queryset
    required_permission = permission or _RESOURCE_PERMISSIONS[normalized]
    if not has_permission(user, required_permission):
        return _deny_all(queryset)

    try:
        scope = _scope_context(user)
        if not scope.valid:
            return _deny_all(queryset)
        modes = _scope_modes(scope, normalized, required_permission)
        if normalized == "parts":
            if not modes:
                return _deny_all(queryset)
            return _scope_parts(queryset, user, modes)
        if "global" in modes:
            return queryset
        if not modes:
            return _deny_all(queryset)
        if normalized == "jobs":
            return _scope_jobs(queryset, scope, modes)
        if normalized == "orders":
            return _scope_orders(queryset, scope, modes)
        if normalized == "customers":
            if "customer" in modes:
                return queryset.filter(id__in=scope.customer_ids)
            return _deny_all(queryset)
        if normalized == "suppliers":
            if "supplier" in modes:
                return queryset.filter(id__in=scope.supplier_ids)
            return _deny_all(queryset)
    except Exception:
        return _deny_all(queryset)
    return _deny_all(queryset)


def permission_scope_modes(
    user: Any,
    permission: str,
    *,
    resource_type: str = "parts",
) -> frozenset[str]:
    """Return the deliberate scope contributions for a canonical permission.

    This is a policy-introspection helper for services, such as protected file
    delivery, that need to apply a narrower category policy to portal and
    assigned-job roles after the ordinary object scope has been enforced.
    """

    normalized = _normalise_resource_type(resource_type)
    if normalized not in _RESOURCE_PERMISSIONS:
        return frozenset()
    if not has_permission(user, permission):
        return frozenset()
    if _uses_legacy_admin_bypass(user):
        return frozenset({"global"})
    try:
        scope = _scope_context(user)
        if not scope.valid:
            return frozenset()
        return _scope_modes(scope, normalized, permission)
    except Exception:
        return frozenset()


def uses_portal_presentation(
    user: Any,
    permission: str,
    *,
    resource_type: str,
) -> bool:
    """Return whether only portal roles contribute the requested authority."""

    modes = permission_scope_modes(
        user,
        permission,
        resource_type=resource_type,
    )
    return bool(modes) and modes <= {"customer", "supplier"}


def order_kind_allowed(user: Any, kind: str, permission: str) -> bool:
    """Return whether the user's contributing order scopes include ``kind``."""

    normalized_kind = str(kind or "").strip().lower()
    if normalized_kind not in {"purchase", "sales"}:
        return False
    if not has_permission(user, permission):
        return False
    if _uses_legacy_admin_bypass(user):
        return True
    try:
        scope = _scope_context(user)
        if not scope.valid:
            return False
        modes = _scope_modes(scope, "orders", permission)
        if "global" in modes:
            return True
        if normalized_kind == "purchase":
            return bool(modes & {"purchase", "supplier"})
        return bool(modes & {"sales", "customer"})
    except Exception:
        return False


def order_relationship_allowed(
    user: Any,
    kind: str,
    relationship: str,
    permission: str,
) -> bool:
    """Authorise a trusted order-to-resource relationship by contributing scope."""

    normalized_kind = str(kind or "").strip().lower()
    normalized_relationship = str(relationship or "").strip().lower()
    if normalized_relationship not in {"customer", "supplier", "job"}:
        return False
    if not order_kind_allowed(user, normalized_kind, permission):
        return False
    if _uses_legacy_admin_bypass(user):
        return True
    try:
        scope = _scope_context(user)
        if not scope.valid:
            return False
        modes = _scope_modes(scope, "orders", permission)
        if "global" in modes:
            return True
        if normalized_kind == "purchase":
            return normalized_relationship in {"supplier", "job"} and bool(
                modes & {"purchase", "supplier"}
            )
        return normalized_relationship in {"customer", "job"} and bool(
            modes & {"sales", "customer"}
        )
    except Exception:
        return False


def authorised_get(
    queryset: Any,
    user: Any,
    identifier: Any,
    *,
    resource_type: str,
    identifier_field: str = "id",
    permission: str | None = None,
) -> Any | None:
    """Scope first, then retrieve one caller-supplied identifier."""

    normalized = _normalise_resource_type(resource_type)
    if normalized not in _RESOURCE_PERMISSIONS:
        raise AuthorizationScopeError(f"Unsupported resource type: {resource_type}")
    try:
        scoped = scope_queryset(queryset, user, normalized, permission=permission)
        result = scoped.filter(**{identifier_field: identifier}).first()
        if result is not None:
            return result
        try:
            exists_unscoped = (
                queryset.filter(**{identifier_field: identifier}).only("id").first()
            )
        except Exception:
            exists_unscoped = None
        if exists_unscoped is not None:
            _denied(
                user,
                reason_code="scope_denied",
                permission=permission or _RESOURCE_PERMISSIONS[normalized],
                resource_type=normalized,
                resource_id=str(identifier or ""),
            )
        return None
    except AuthorizationScopeError:
        raise
    except Exception:
        return None


def _part_resource_id(part_number: Any, revision: Any) -> str:
    return f"{str(part_number or '').strip().casefold()}:{str(revision or '').strip().casefold()}"


def part_is_released(part: Any) -> bool:
    """Return the application's canonical approval/release state for a part.

    Reads the boolean resolved on write, matching ``approval_filter_raw`` so a
    part visible through a scoped query is never judged differently here. Any
    other state is unapproved, which fails closed for portal visibility.
    """

    try:
        return bool((getattr(part, "canonical", None) or {}).get("approved"))
    except Exception:
        return False


def authorised_part_pairs(
    user: Any,
    pairs: Iterable[tuple[Any, Any]],
    *,
    permission: str = "parts.read",
) -> frozenset[tuple[str, str]]:
    """Return only exact requested identities present in the caller's part scope."""

    normalized: dict[tuple[str, str], tuple[str, str]] = {}
    for part_number, revision in pairs:
        pn = str(part_number or "").strip()
        rev = str(revision or "").strip()
        if not pn:
            continue
        key = (pn.casefold(), rev.casefold())
        normalized[key] = (pn, rev)
    if not normalized:
        return frozenset()
    try:
        from mongoengine.queryset.visitor import Q
        from app.models.part import Part

        scoped = scope_queryset(Part.objects, user, "parts", permission=permission)

        # Fetch by part_number with an indexable $in, then match the exact
        # (pn, rev) identity case-insensitively in Python.
        #
        # This used to build one case-insensitive $regex clause PER PAIR inside
        # a single $or. Regex anchors like that cannot use an index, so Mongo
        # collection-scanned once per clause: a 2034-node BOM walk spent about
        # 16 seconds in this one function. The identity semantics are unchanged
        # - only exact case-insensitive matches are returned - but the database
        # now does a single indexed lookup and the comparison happens in memory.
        # One case-insensitive $in over part_number only, instead of one anchored
        # $regex per (pn, rev) pair. Revision is matched in Python below, so the
        # database does a single lookup rather than a collection scan per clause.
        wanted_names = {pn for pn, _rev in normalized.values()}
        found = scoped.filter(
            Q(__raw__={
                "part_number": {
                    "$in": [
                        re.compile(f"^{re.escape(name)}$", re.IGNORECASE)
                        for name in wanted_names
                    ]
                }
            })
        ).only("part_number", "revision")
        available = {
            (
                str(part.part_number or "").strip().casefold(),
                str(part.revision or "").strip().casefold(),
            )
            for part in found
        }
        return frozenset(key for key in normalized if key in available)
    except Exception:
        return frozenset()


def authorise_part_access(
    user: Any,
    part_number: Any,
    revision: Any,
    *,
    allow_part_family: bool = False,
) -> AuthorizationDecision:
    pn = str(part_number or "").strip()
    rev = str(revision or "").strip()
    resource_id = _part_resource_id(pn, rev)
    permission = authorise(
        user,
        "parts.read",
        context={"resource_type": "part", "resource_id": resource_id},
    )
    if not permission.allowed:
        return permission
    reason = "resource_out_of_scope"
    try:
        from app.models.part import Part

        if pn:
            query = scope_queryset(Part.objects, user, "parts").filter(
                part_number__iexact=pn
            )
            if not allow_part_family:
                query = query.filter(revision__iexact=rev)
            if query.only("id").first() is not None:
                return AuthorizationDecision(
                    True, "allowed", "parts.read", "part", resource_id,
                    permission.used_legacy_admin_bypass,
                )
    except Exception:
        reason = "authorisation_error"
    return _denied(
        user,
        reason_code=reason,
        permission="parts.read",
        resource_type="part",
        resource_id=resource_id,
        used_legacy_admin_bypass=permission.used_legacy_admin_bypass,
    )


def enforce_permission(permission: str, *, user: Any = None) -> None:
    """Abort unless the user holds the permission, recording why.

    The imperative counterpart to :func:`require_permission`, for checks that
    depend on the request body rather than the route.
    """

    actor = current_user if user is None else user
    if not _is_authenticated(actor):
        abort(401)
    decision = authorise(actor, permission)
    if not decision.allowed:
        g.authz_denial = decision
        abort(403)


def require_permission(permission: str):
    """Require one canonical permission for a route."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            enforce_permission(permission)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
