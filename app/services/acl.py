"""Legacy import surface backed by the central authorization service."""

from __future__ import annotations

from functools import wraps
from typing import Optional, Set, Tuple

from flask import abort, g
from flask_login import current_user


def user_has_permission(user, permission: str) -> bool:
    from app.services.authorization import has_permission

    return has_permission(user, permission)


def customer_scope_ids(user) -> list:
    from app.services.authorization import relationship_ids

    return list(relationship_ids(user, "customer"))


def supplier_scope_ids(user) -> list:
    from app.services.authorization import relationship_ids

    return list(relationship_ids(user, "supplier"))


def apply_job_scope(queryset, user):
    from app.services.authorization import scope_queryset

    return scope_queryset(queryset, user, "jobs")


def apply_order_scope(queryset, user):
    from app.services.authorization import scope_queryset

    return scope_queryset(queryset, user, "orders")


def allowed_parts_for(user) -> Optional[Set[Tuple[str, str]]]:
    from app.services.authorization import relationship_part_pairs

    return relationship_part_pairs(user)


def part_is_allowed(
    allowed: Optional[Set[Tuple[str, str]]],
    part_number: str,
    revision: str | None,
) -> bool:
    if allowed is None:
        return True
    key = (
        str(part_number or "").strip().casefold(),
        str(revision or "").strip().casefold(),
    )
    return any(
        key
        == (
            str(allowed_pn or "").strip().casefold(),
            str(allowed_rev or "").strip().casefold(),
        )
        for allowed_pn, allowed_rev in allowed
    )


def permissions_required(*permissions: str):
    """Compatibility decorator requiring every supplied permission."""

    def decorate(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not getattr(current_user, "is_authenticated", False):
                abort(401)
            from app.services.authorization import authorise

            for permission in permissions:
                decision = authorise(current_user, permission)
                if not decision.allowed:
                    g.authz_denial = decision
                    abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorate
