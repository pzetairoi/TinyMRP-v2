"""Small, fail-closed backend authorisation primitives.

This module supplies the Stage 2 API without migrating route-level object
lookups or serializers. It contains no policy language and no process-wide
cache of users, roles, or permissions.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import wraps
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
    LEGACY_PERMISSION_COMPATIBILITY,
    LEGACY_PERMISSIONS,
    PERMISSION_REGISTRY,
)


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason_code: str
    permission: str
    resource_type: str = ""
    resource_id: str = ""
    used_legacy_expansion: bool = False
    used_legacy_admin_bypass: bool = False
    conflict_code: str = ""


@dataclass(frozen=True)
class ConflictDecision:
    allowed: bool
    reason_code: str = ""
    conflict_code: str = ""


@dataclass(frozen=True)
class _PermissionSnapshot:
    direct: frozenset[str]
    expanded: frozenset[str]
    role_names: frozenset[str]
    role_permissions: tuple[tuple[str, frozenset[str]], ...] = ()


@dataclass(frozen=True)
class _ScopeContext:
    valid: bool
    customer_ids: tuple[Any, ...] = ()
    supplier_ids: tuple[Any, ...] = ()
    participant_job_ids: tuple[Any, ...] = ()
    role_names: frozenset[str] = frozenset()
    role_permissions: tuple[tuple[str, frozenset[str]], ...] = ()


class AuthorizationScopeError(RuntimeError):
    """Raised when a scope policy does not exist for a resource type."""


_EMPTY_SNAPSHOT = _PermissionSnapshot(frozenset(), frozenset(), frozenset(), ())
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

# Stage 2 proves the hook. Complete portal/customer/supplier policies are
# deliberately deferred to Stage 3.
FIELD_FILTER_POLICIES: dict[str, frozenset[str]] = {
    "parts": frozenset({"part_number", "revision", "description", "status"}),
    "jobs": frozenset(
        {
            "id",
            "job_number",
            "title",
            "description",
            "part_number",
            "part_revision",
            "status",
        }
    ),
    "orders": frozenset({"id", "order_number", "description", "kind", "status"}),
    "customers": frozenset({"id", "code", "name", "description", "status"}),
    "suppliers": frozenset({"id", "code", "name", "description", "status"}),
}

TRANSACTION_CONFLICT_ACTIONS = frozenset(
    {
        "import_self_approval",
        "order_self_approval",
        "design_self_approval",
        "security_self_escalation",
        "last_security_admin_removal",
        "last_system_admin_removal",
    }
)
_TRANSACTION_CONFLICT_RULES: dict[
    str, Callable[[Any, Any, Mapping[str, Any]], str | bool | None] | None
] = {action: None for action in TRANSACTION_CONFLICT_ACTIONS}


def _is_authenticated(user: Any) -> bool:
    try:
        return bool(user is not None and getattr(user, "is_authenticated", False))
    except Exception:
        return False


def _cache_key(user: Any) -> str:
    try:
        user_id = getattr(user, "id", None)
        if user_id is not None:
            return f"id:{user_id}"
    except Exception:
        pass
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
    try:
        roles = tuple(getattr(user, "roles", None) or ())
        for role in roles:
            if role is None:
                continue
            try:
                if getattr(role, "active", True) is False:
                    continue
                name = getattr(role, "name", None)
                permissions = getattr(role, "permissions", None) or ()
                if isinstance(permissions, (str, bytes)):
                    continue
                permission_values = tuple(permissions)
                if isinstance(name, str) and name:
                    role_names.add(name)
                valid_permissions = {
                    permission
                    for permission in permission_values
                    if isinstance(permission, str) and permission in PERMISSION_REGISTRY
                }
                role_expanded = set(valid_permissions)
                for permission in valid_permissions & LEGACY_PERMISSIONS:
                    role_expanded.update(LEGACY_PERMISSION_COMPATIBILITY.get(permission, ()))
                if isinstance(name, str) and name:
                    role_permissions.append((name, frozenset(role_expanded)))
                for permission in permission_values:
                    if isinstance(permission, str) and permission in PERMISSION_REGISTRY:
                        direct.add(permission)
            except Exception:
                continue
    except Exception:
        return _EMPTY_SNAPSHOT

    expanded = set(direct)
    for permission in direct & LEGACY_PERMISSIONS:
        expanded.update(LEGACY_PERMISSION_COMPATIBILITY.get(permission, ()))
    return _PermissionSnapshot(
        direct=frozenset(direct),
        expanded=frozenset(expanded),
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


def effective_permissions(user: Any, *, include_legacy: bool = True) -> frozenset[str]:
    """Return the immutable union of all valid permissions assigned to a user."""

    try:
        snapshot = _permission_snapshot(user)
        return snapshot.expanded if include_legacy else snapshot.direct
    except Exception:
        return frozenset()


def legacy_admin_bypass_enabled() -> bool:
    """Return the temporary Stage 2 compatibility setting (remove in Stage 9)."""

    try:
        if has_app_context():
            return bool(current_app.config.get("LEGACY_ADMIN_BYPASS_ENABLED", True))
    except Exception:
        return False
    return True


def _uses_legacy_admin_bypass(user: Any) -> bool:
    if not _is_authenticated(user) or not legacy_admin_bypass_enabled():
        return False
    try:
        return "admin" in _permission_snapshot(user).role_names
    except Exception:
        return False


def has_permission(
    user: Any,
    permission: str,
    *,
    include_legacy: bool = True,
) -> bool:
    """Return whether a registered permission is effective for the user."""

    try:
        if not isinstance(permission, str) or permission not in PERMISSION_REGISTRY:
            return False
        if not _is_authenticated(user):
            return False
        if _uses_legacy_admin_bypass(user):
            return True
        return permission in effective_permissions(user, include_legacy=include_legacy)
    except Exception:
        return False


def has_all_permissions(
    user: Any,
    permissions: Iterable[str],
    *,
    include_legacy: bool = True,
) -> bool:
    try:
        values = tuple(permissions)
        return all(
            has_permission(user, permission, include_legacy=include_legacy)
            for permission in values
        )
    except Exception:
        return False


def has_any_permission(
    user: Any,
    permissions: Iterable[str],
    *,
    include_legacy: bool = True,
) -> bool:
    try:
        values = tuple(permissions)
        return any(
            has_permission(user, permission, include_legacy=include_legacy)
            for permission in values
        )
    except Exception:
        return False


def _resource_identity(
    resource: Any,
    context: Mapping[str, Any] | None,
) -> tuple[str, str]:
    resource_type = ""
    resource_id = ""
    try:
        if context:
            resource_type = str(context.get("resource_type") or "")
            resource_id = str(context.get("resource_id") or "")
        if resource is not None:
            if not resource_type:
                resource_type = type(resource).__name__.lower()
            if not resource_id:
                resource_id = str(getattr(resource, "id", "") or "")
    except Exception:
        return "", ""
    return resource_type, resource_id


def _denied(
    user: Any,
    *,
    reason_code: str,
    permission: str,
    resource_type: str = "",
    resource_id: str = "",
    used_legacy_expansion: bool = False,
    used_legacy_admin_bypass: bool = False,
    conflict_code: str = "",
) -> AuthorizationDecision:
    decision = AuthorizationDecision(
        allowed=False,
        reason_code=reason_code,
        permission=permission,
        resource_type=resource_type,
        resource_id=resource_id,
        used_legacy_expansion=used_legacy_expansion,
        used_legacy_admin_bypass=used_legacy_admin_bypass,
        conflict_code=conflict_code,
    )
    try:
        log_authorization_denial(user, decision)
    except Exception:
        pass
    return decision


def authorise(
    user: Any,
    permission: str,
    *,
    resource: Any = None,
    context: Mapping[str, Any] | None = None,
) -> AuthorizationDecision:
    """Make a structured, fail-closed permission and conflict decision."""

    resource_type, resource_id = _resource_identity(resource, context)
    if not isinstance(permission, str) or permission not in PERMISSION_REGISTRY:
        return _denied(
            user,
            reason_code="invalid_permission",
            permission=str(permission or ""),
            resource_type=resource_type,
            resource_id=resource_id,
        )
    if not _is_authenticated(user):
        return _denied(
            user,
            reason_code="unauthenticated",
            permission=permission,
            resource_type=resource_type,
            resource_id=resource_id,
        )

    try:
        snapshot = _permission_snapshot(user)
        used_admin = _uses_legacy_admin_bypass(user)
        used_legacy = permission not in snapshot.direct and permission in snapshot.expanded
        if not used_admin and permission not in snapshot.expanded:
            return _denied(
                user,
                reason_code="missing_permission",
                permission=permission,
                resource_type=resource_type,
                resource_id=resource_id,
            )

        conflict_action = str((context or {}).get("conflict_action") or "")
        if conflict_action:
            conflict = check_transaction_conflict(
                user,
                conflict_action,
                resource=resource,
                context=context,
            )
            if not conflict.allowed:
                return _denied(
                    user,
                    reason_code="transaction_conflict",
                    permission=permission,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    used_legacy_expansion=used_legacy,
                    used_legacy_admin_bypass=used_admin,
                    conflict_code=conflict.conflict_code,
                )

        return AuthorizationDecision(
            allowed=True,
            reason_code="allowed",
            permission=permission,
            resource_type=resource_type,
            resource_id=resource_id,
            used_legacy_expansion=used_legacy,
            used_legacy_admin_bypass=used_admin,
        )
    except Exception:
        return _denied(
            user,
            reason_code="authorisation_error",
            permission=permission,
            resource_type=resource_type,
            resource_id=resource_id,
        )


def log_authorization_denial(user: Any, decision: AuthorizationDecision) -> None:
    """Best-effort structured denial audit; logging failure never grants access."""

    if decision.allowed:
        return
    try:
        endpoint = ""
        method = ""
        if has_request_context():
            endpoint = str(request.endpoint or request.path or "")
            method = str(request.method or "")
        actor_id = str(getattr(user, "id", "") or "") if user is not None else ""
        fingerprint = (
            actor_id,
            decision.permission,
            decision.resource_type,
            decision.resource_id,
            decision.reason_code,
            endpoint,
            method,
        )
        cache = _request_cache("denial_events")
        if cache is not None and str(fingerprint) in cache:
            return
        if cache is not None:
            cache[str(fingerprint)] = True

        from app.services.audit import log_action

        log_action(
            "authorization.denied",
            resource_type=decision.resource_type or "authorization",
            resource=decision.resource_id,
            meta={
                "actor_id": actor_id,
                "permission": decision.permission,
                "reason_code": decision.reason_code,
                "endpoint": endpoint,
                "method": method,
                "used_legacy_expansion": decision.used_legacy_expansion,
                "used_legacy_admin_bypass": decision.used_legacy_admin_bypass,
                "conflict_code": decision.conflict_code,
            },
        )
    except Exception:
        return


def _build_scope_context(user: Any) -> _ScopeContext:
    if not _is_authenticated(user):
        return _ScopeContext(valid=False)
    try:
        from app.models.customer import Customer
        from app.models.job import Job
        from app.models.supplier import Supplier

        customer_ids = tuple(c.id for c in Customer.objects(users=user).only("id"))
        supplier_ids = tuple(s.id for s in Supplier.objects(users=user).only("id"))
        participant_ids = tuple(
            j.id for j in Job.objects(participants=user, is_deleted=False).only("id")
        )
        return _ScopeContext(
            valid=True,
            customer_ids=customer_ids,
            supplier_ids=supplier_ids,
            participant_job_ids=participant_ids,
            role_names=_permission_snapshot(user).role_names,
            role_permissions=_permission_snapshot(user).role_permissions,
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
    try:
        return queryset.filter(id__in=[])
    except Exception as exc:
        try:
            return queryset.none()
        except Exception:
            raise AuthorizationScopeError("Unable to construct a deny-all queryset") from exc


def _scope_modes(
    scope: _ScopeContext,
    resource_type: str,
    permission: str,
) -> frozenset[str]:
    """Return the union of scope contributions from roles granting permission."""

    modes: set[str] = set()
    for role_name, permissions in scope.role_permissions:
        if permission not in permissions:
            continue
        if role_name in {"customer_portal", "customer_viewer"}:
            modes.add("customer")
            continue
        if role_name in {"supplier_portal", "supplier_viewer"}:
            modes.add("supplier")
            continue
        if role_name in {"production_operator", "operator"}:
            modes.add("assigned")
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
        if resource_type == "orders" and role_name == "procurement":
            modes.add("purchase")
            continue
        if resource_type == "orders" and role_name == "sales_customer_service":
            modes.add("sales")
            continue
        modes.add("global")
    return frozenset(modes)


def _scope_jobs(queryset: Any, scope: _ScopeContext, modes: frozenset[str]) -> Any:
    from mongoengine.queryset.visitor import Q

    query = Q()
    has_clause = False
    if "customer" in modes and scope.customer_ids:
        query |= Q(customer__in=scope.customer_ids)
        has_clause = True
    if "assigned" in modes and scope.participant_job_ids:
        query |= Q(id__in=scope.participant_job_ids)
        has_clause = True
    if "supplier" in modes and scope.supplier_ids:
        from app.models.order import Order

        order_job_ids = tuple(
            order.job.id
            for order in Order.objects(supplier__in=scope.supplier_ids).only("job")
            if getattr(order, "job", None)
        )
        if order_job_ids:
            query |= Q(id__in=order_job_ids)
            has_clause = True
    return queryset.filter(query) if has_clause else _deny_all(queryset)


def _scope_orders(queryset: Any, scope: _ScopeContext, modes: frozenset[str]) -> Any:
    from mongoengine.queryset.visitor import Q

    query = Q()
    has_clause = False
    if "purchase" in modes:
        query |= Q(kind="purchase")
        has_clause = True
    if "sales" in modes:
        query |= Q(kind="sales")
        has_clause = True
    if "supplier" in modes and scope.supplier_ids:
        query |= Q(kind="purchase", supplier__in=scope.supplier_ids)
        has_clause = True
    if "customer" in modes and scope.customer_ids:
        query |= Q(kind="sales", customer__in=scope.customer_ids)
        has_clause = True
        from app.models.job import Job

        customer_job_ids = tuple(
            job.id
            for job in Job.objects(
                customer__in=scope.customer_ids,
                is_deleted=False,
            ).only("id")
        )
        if customer_job_ids:
            query |= Q(kind="sales", job__in=customer_job_ids)
    if "assigned" in modes and scope.participant_job_ids:
        query |= Q(job__in=scope.participant_job_ids)
        has_clause = True
    return queryset.filter(query) if has_clause else _deny_all(queryset)


def _scope_parts(queryset: Any, user: Any) -> Any:
    from mongoengine.queryset.visitor import Q
    from app.services.acl import allowed_parts_for

    allowed = allowed_parts_for(user)
    if allowed is None or not allowed:
        return _deny_all(queryset)
    query = Q()
    has_clause = False
    for part_number, revision in allowed:
        pn = str(part_number or "").strip()
        rev = str(revision or "").strip()
        if not pn:
            continue
        query |= Q(part_number__iexact=pn, revision__iexact=rev)
        has_clause = True
    return queryset.filter(query) if has_clause else _deny_all(queryset)


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
        if "global" in modes:
            return queryset
        if not modes:
            return _deny_all(queryset)
        if normalized == "parts":
            return _scope_parts(queryset, user)
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


def authorise_part_access(
    user: Any,
    part_number: Any,
    revision: Any,
    *,
    allow_part_family: bool = False,
) -> AuthorizationDecision:
    """Authorise exact ``(part_number, revision)`` access.

    ``allow_part_family`` is explicit and separate; a blank revision is never
    treated as a wildcard by the default exact-revision path.
    """

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
    if not pn:
        return _denied(
            user,
            reason_code="resource_out_of_scope",
            permission="parts.read",
            resource_type="part",
            resource_id=resource_id,
            used_legacy_expansion=permission.used_legacy_expansion,
            used_legacy_admin_bypass=permission.used_legacy_admin_bypass,
        )

    try:
        from app.models.part import Part

        scoped = scope_queryset(Part.objects, user, "parts")
        query = scoped.filter(part_number__iexact=pn)
        if not allow_part_family:
            query = query.filter(revision__iexact=rev)
        if query.first() is not None:
            return AuthorizationDecision(
                allowed=True,
                reason_code="allowed",
                permission="parts.read",
                resource_type="part",
                resource_id=resource_id,
                used_legacy_expansion=permission.used_legacy_expansion,
                used_legacy_admin_bypass=permission.used_legacy_admin_bypass,
            )
    except Exception:
        return _denied(
            user,
            reason_code="authorisation_error",
            permission="parts.read",
            resource_type="part",
            resource_id=resource_id,
            used_legacy_expansion=permission.used_legacy_expansion,
            used_legacy_admin_bypass=permission.used_legacy_admin_bypass,
        )
    return _denied(
        user,
        reason_code="resource_out_of_scope",
        permission="parts.read",
        resource_type="part",
        resource_id=resource_id,
        used_legacy_expansion=permission.used_legacy_expansion,
        used_legacy_admin_bypass=permission.used_legacy_admin_bypass,
    )


def _is_external_field_context(user: Any) -> tuple[bool, bool]:
    if _uses_legacy_admin_bypass(user):
        return True, False
    try:
        scope = _scope_context(user)
        if not scope.valid:
            return False, True
        external = not any(
            "global" in _scope_modes(scope, resource_type, permission)
            for resource_type, permission in _RESOURCE_PERMISSIONS.items()
        )
        return True, external
    except Exception:
        return False, True


def filter_response_fields(
    resource_type: str,
    user: Any,
    payload: Mapping[str, Any],
    *,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Copy and minimally filter a response payload.

    Stage 3 will replace the example external allowlists with complete domain
    policies. Unsupported or failed external policies return no fields.
    """

    if not isinstance(payload, Mapping):
        return {}
    copied = deepcopy(dict(payload))
    normalized = _normalise_resource_type(resource_type)
    valid, external = _is_external_field_context(user)
    if context and bool(context.get("force_external")):
        external = True
    if not valid:
        return {}
    policy = FIELD_FILTER_POLICIES.get(normalized)
    if policy is None:
        return {}
    if not external:
        return copied
    return {key: value for key, value in copied.items() if key in policy}


def check_transaction_conflict(
    user: Any,
    action: str,
    resource: Any = None,
    context: Mapping[str, Any] | None = None,
) -> ConflictDecision:
    """Run a registered transaction rule; unknown/error cases deny."""

    if action not in TRANSACTION_CONFLICT_ACTIONS:
        return ConflictDecision(
            allowed=False,
            reason_code="transaction_conflict",
            conflict_code="unknown_transaction_action",
        )
    rule = _TRANSACTION_CONFLICT_RULES.get(action)
    if rule is None:
        return ConflictDecision(allowed=True, reason_code="no_conflict")
    try:
        result = rule(user, resource, context or {})
        if not result:
            return ConflictDecision(allowed=True, reason_code="no_conflict")
        code = result if isinstance(result, str) else action
        return ConflictDecision(
            allowed=False,
            reason_code="transaction_conflict",
            conflict_code=str(code),
        )
    except Exception:
        return ConflictDecision(
            allowed=False,
            reason_code="transaction_conflict",
            conflict_code="conflict_check_error",
        )


def require_permission(
    permission: str,
    *,
    resource_loader: Callable[..., Any] | None = None,
    scope_resolver: Callable[[Any, Any], bool] | None = None,
):
    """Decorator for future route migration without changing route contracts."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not _is_authenticated(current_user):
                abort(401)
            resource = None
            try:
                if resource_loader is not None:
                    resource = resource_loader(*args, **kwargs)
                decision = authorise(current_user, permission, resource=resource)
                if not decision.allowed:
                    abort(403)
                if scope_resolver is not None and not scope_resolver(current_user, resource):
                    denied = _denied(
                        current_user,
                        reason_code="resource_out_of_scope",
                        permission=permission,
                        resource_type=decision.resource_type,
                        resource_id=decision.resource_id,
                    )
                    if not denied.allowed:
                        abort(404)
            except AuthorizationScopeError:
                abort(404)
            except Exception as exc:
                if getattr(exc, "code", None) in {401, 403, 404}:
                    raise
                denied = _denied(
                    current_user,
                    reason_code="authorisation_error",
                    permission=permission,
                )
                if not denied.allowed:
                    abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
