# app/services/purge.py — selective destructive maintenance.
"""Independently purgeable slices of user-entered data.

One declarative registry drives the admin UI, the permission checks and the
execution, so adding a target is a single table entry rather than a new form,
route branch and handler.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from app.models.artifact import PartFile
from app.models.auth import Role, User
from app.models.bom import BOMLink
from app.models.customer import Customer
from app.models.extra_file import PartExtraFile
from app.models.job import Job
from app.models.notification import UserNotification
from app.models.order import Order
from app.models.part import Part
from app.models.part_annotation import PartAnnotation
from app.models.part_drawing_markup import PartDrawingMarkup
from app.models.part_share import PartShareLink
from app.models.supplier import Supplier
from app.services.session_lifecycle import revoke_user_sessions
from app.services.standard_roles import STANDARD_ROLES

# Least-privileged general role used when a purge would otherwise leave a user
# with no roles at all.
_FALLBACK_ROLE = "internal"


@dataclass(frozen=True)
class PurgeTarget:
    key: str
    label: str
    description: str
    group: str
    permissions: tuple[str, ...]
    count: Callable[[], int]
    run: Callable[[], int]
    # Targets whose data becomes orphaned unless they are purged together.
    warns: tuple[str, ...] = ()
    # Irreversible losses of operator-entered work that no rescan or re-import
    # can rebuild. Selecting one requires typing the confirmation phrase.
    confirm: bool = False


def _count(model) -> Callable[[], int]:
    return lambda: model.objects.count()


def _delete(model) -> Callable[[], int]:
    return lambda: int(model.objects.delete() or 0)


def _clear_part_properties() -> int:
    """Strip user-entered attributes while keeping the part records.

    Updated in place rather than loaded and saved: a projected document would
    fail model validation on the required fields it did not load.
    """
    return int(
        Part.objects.update(set__attrs={}, set__canonical={}, set__field_values={}) or 0
    )


def _clear_review_flags() -> None:
    """Reset the materialized pending-review counters.

    The parts grid filters on ``pending_review_count`` in Mongo rather than
    recomputing per row, which is what keeps the inventory fast. Deleting the
    underlying comments or markups must therefore clear the counters too, or
    parts stay flagged for reviews that no longer exist.
    """
    Part.objects(pending_review_count__gt=0).update(
        set__pending_review_count=0, set__pending_review_severity=""
    )


def _delete_annotations() -> int:
    removed = int(PartAnnotation.objects.delete() or 0)
    _clear_review_flags()
    return removed


def _delete_markups() -> int:
    removed = int(PartDrawingMarkup.objects.delete() or 0)
    _clear_review_flags()
    return removed


def _custom_roles() -> Any:
    """Roles an operator created, i.e. everything outside the standard set."""
    return Role.objects(name__nin=list(STANDARD_ROLES))


def _delete_custom_roles() -> int:
    """Remove custom roles, demoting anyone left without one.

    A user stripped of their only role would otherwise be left with no access
    at all, so they fall back to the least-privileged general role rather than
    becoming unusable accounts.
    """
    roles = list(_custom_roles())
    if not roles:
        return 0
    fallback = Role.objects(name=_FALLBACK_ROLE).first()
    affected = list(User.objects(roles__in=roles))
    removed = int(Role.objects(id__in=[role.id for role in roles]).delete() or 0)
    dropped = {role.id for role in roles}
    for user in affected:
        kept = [role for role in (user.roles or []) if role and role.id not in dropped]
        if not kept and fallback is not None:
            kept = [fallback]
        user.roles = kept
        user.save()
        revoke_user_sessions(user, reason="custom_roles_purged")
    return removed


def _non_admin_users() -> Any:
    """Every user without an administrator role.

    Administrators are always excluded so a purge can never lock the instance
    out of its own admin surface.
    """
    admin_roles = [role for role in Role.objects(name="administrator")]
    query = User.objects
    return query.filter(roles__nin=admin_roles) if admin_roles else query


TARGETS: tuple[PurgeTarget, ...] = (
    PurgeTarget(
        "part_files", "Part files", "File records pointing at deliverables. Files on disk are not touched.",
        "Parts", ("files.purge",), _count(PartFile), _delete(PartFile),
    ),
    PurgeTarget(
        "extra_files", "Associated files", "Records for uploaded associated files.",
        "Parts", ("files.purge",), _count(PartExtraFile), _delete(PartExtraFile),
    ),
    PurgeTarget(
        "bom", "BOM links", "Every parent/child relationship.",
        "Parts", ("parts.purge",), _count(BOMLink), _delete(BOMLink),
    ),
    PurgeTarget(
        "annotations", "Comments & notes", "Part comments, replies and notes.",
        "Parts", ("parts.purge",), _count(PartAnnotation), _delete_annotations,
        confirm=True,
    ),
    PurgeTarget(
        "markups", "Drawing markups", "Saved drawing markup documents.",
        "Parts", ("parts.purge",), _count(PartDrawingMarkup), _delete_markups,
        confirm=True,
    ),
    PurgeTarget(
        "shares", "Part shares", "Public share links for parts.",
        "Parts", ("parts.purge",), _count(PartShareLink), _delete(PartShareLink),
    ),
    PurgeTarget(
        "part_properties", "Part properties", "Clears attributes but keeps the part entries.",
        "Parts", ("parts.purge",),
        lambda: Part.objects(attrs__ne={}).count(), _clear_part_properties,
        confirm=True,
    ),
    PurgeTarget(
        "parts", "Part entries", "The part records themselves.",
        "Parts", ("parts.purge",), _count(Part), _delete(Part),
        warns=("bom", "part_files", "extra_files", "annotations", "markups", "shares"),
        confirm=True,
    ),
    PurgeTarget(
        "orders", "Orders", "Sales and purchase orders.",
        "Business", ("orders.archive",), _count(Order), _delete(Order),
        confirm=True,
    ),
    PurgeTarget(
        "jobs", "Jobs", "Jobs and their BOM assignments. Orders are unlinked, not deleted.",
        "Business", ("jobs.archive",), _count(Job), _delete(Job),
        confirm=True,
    ),
    PurgeTarget(
        "customers", "Customers", "Customer organisations and their user links.",
        "Business", ("customers.archive",), _count(Customer), _delete(Customer),
        confirm=True,
    ),
    PurgeTarget(
        "suppliers", "Suppliers", "Supplier organisations and their user links.",
        "Business", ("suppliers.archive",), _count(Supplier), _delete(Supplier),
        confirm=True,
    ),
    PurgeTarget(
        "notifications", "Notifications", "Queued and delivered user notifications.",
        "System", ("system.maintenance",), _count(UserNotification), _delete(UserNotification),
    ),
    PurgeTarget(
        "custom_roles", "Custom roles",
        f"Roles outside the standard set. Users left without a role fall back to “{_FALLBACK_ROLE}”.",
        "System", ("security.roles.manage",),
        lambda: _custom_roles().count(), _delete_custom_roles,
        confirm=True,
    ),
    PurgeTarget(
        "users", "Non-admin users", "Every user except administrators.",
        "System", ("security.users.manage",),
        lambda: _non_admin_users().count(),
        lambda: int(_non_admin_users().delete() or 0),
        confirm=True,
    ),
)

BY_KEY: Dict[str, PurgeTarget] = {target.key: target for target in TARGETS}


def available(user, has_permission) -> List[Dict[str, Any]]:
    """Targets the actor may run, with live counts for the confirm screen."""
    rows = []
    for target in TARGETS:
        if not all(has_permission(user, name) for name in target.permissions):
            continue
        try:
            count = int(target.count() or 0)
        except Exception:
            count = 0
        rows.append(
            {
                "key": target.key,
                "label": target.label,
                "description": target.description,
                "group": target.group,
                "count": count,
                "warns": [BY_KEY[dep].label for dep in target.warns if dep in BY_KEY],
                "confirm": target.confirm,
            }
        )
    return rows


# Typed by the operator before an irreversible target runs.
CONFIRM_PHRASE = "DELETE"


def requires_confirmation(keys) -> List[str]:
    """Labels of the selected targets that need the typed phrase."""
    selected = {str(key) for key in keys or ()}
    return [t.label for t in TARGETS if t.key in selected and t.confirm]


def run(keys, user, has_permission, *, confirmation: str = "") -> Dict[str, int]:
    """Execute the selected targets, skipping any the actor cannot run.

    Order follows the registry so dependent records are removed before the
    entries they hang off, leaving no orphans behind. Irreversible targets are
    refused unless the typed phrase matches, enforced here rather than in the
    template so the check cannot be bypassed by posting the form directly.
    """
    results: Dict[str, int] = {}
    selected = {str(key) for key in keys or ()}
    typed_ok = str(confirmation or "").strip() == CONFIRM_PHRASE
    for target in TARGETS:
        if target.key not in selected:
            continue
        if not all(has_permission(user, name) for name in target.permissions):
            continue
        if target.confirm and not typed_ok:
            continue
        results[target.key] = int(target.run() or 0)
    return results
