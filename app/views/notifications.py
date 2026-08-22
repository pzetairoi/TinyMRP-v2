from __future__ import annotations

from flask import Blueprint, jsonify, request
from mongoengine.queryset.visitor import Q

from app.models.auth import User
from app.models.notification import UserNotification
from app.models.part import Part
from app.services.api_auth import api_auth_required, get_request_user
from app.services.authorization import (
    authorise_part_access,
    has_permission,
    uses_portal_presentation,
)
from app.services.notifications import notification_lifecycle, persist_notification_lifecycle
from app.services.timezone_utils import utc_iso, utc_now
from app.services.user_profile import profile_for_user


bp = Blueprint("notifications_api", __name__, url_prefix="/api")


def _payload(row: UserNotification, lifecycle: str = "", lifecycle_reason: str = "") -> dict:
    payload = {
        "id": str(row.id),
        "kind": row.kind,
        "title": row.title,
        "body": row.body,
        "url": row.url,
        "actor_email": row.actor_email,
        "part_number": row.part_number,
        "revision": row.revision,
        "thread_id": row.thread_id,
        "comment_id": row.comment_id,
        "created_at": utc_iso(row.created_at),
        "read_at": utc_iso(row.read_at),
        "unread": row.read_at is None,
    }
    if lifecycle:
        payload["lifecycle"] = lifecycle
        payload["lifecycle_reason"] = lifecycle_reason
    return payload


@bp.get("/notifications")
@api_auth_required
def notifications_list():
    user = get_request_user()
    try:
        limit = max(1, min(100, int(request.args.get("limit") or 20)))
    except (TypeError, ValueError):
        limit = 20
    view = str(request.args.get("view") or "current").strip().lower()
    if view not in {"current", "history", "all"}:
        return jsonify({"ok": False, "error": "invalid_view"}), 400
    base_query = UserNotification.objects(recipient=user)
    if str(request.args.get("unread_only") or "").lower() in ("1", "true", "yes"):
        base_query = base_query.filter(read_at=None)

    # Existing installations predate lifecycle fields. Classify those events
    # once, then persist the result so normal bell polling remains indexed and
    # bounded. Rechecking the small current set also catches out-of-band deletes.
    while True:
        unclassified = list(
            base_query.filter(Q(lifecycle="") | Q(lifecycle__exists=False))
            .order_by("-created_at")[:500]
        )
        if not unclassified:
            break
        legacy_current, legacy_history = notification_lifecycle(
            unclassified,
            user,
        )
        persist_notification_lifecycle(legacy_current, "current")
        persist_notification_lifecycle(legacy_history, "history")

    verification_limit = max(100, limit * 2)
    current_candidates = list(
        base_query.filter(lifecycle="current").order_by("-created_at")[:verification_limit]
    )
    verified_current, newly_historical = notification_lifecycle(current_candidates, user)
    persist_notification_lifecycle(verified_current, "current")
    persist_notification_lifecycle(newly_historical, "history")

    current_query = base_query.filter(lifecycle="current").order_by("-created_at")
    history_query = base_query.filter(
        lifecycle="history",
        lifecycle_reason__ne="inaccessible",
    ).order_by("-created_at")
    current_count = current_query.count()
    history_count = history_query.count()
    current_unread_count = current_query.filter(read_at=None).count()
    if view == "current":
        payload_rows = [
            _payload(row, "current", row.lifecycle_reason)
            for row in current_query[:limit]
        ]
    elif view == "history":
        payload_rows = [
            _payload(row, "history", row.lifecycle_reason)
            for row in history_query[:limit]
        ]
    else:
        combined = list(current_query[:limit]) + list(history_query[:limit])
        combined.sort(key=lambda row: row.created_at, reverse=True)
        payload_rows = [
            _payload(row, row.lifecycle, row.lifecycle_reason)
            for row in combined[:limit]
        ]
    return jsonify({
        "ok": True,
        "view": view,
        "unread_count": current_unread_count,
        "current_count": current_count,
        "history_count": history_count,
        "notifications": payload_rows,
    })


@bp.post("/notifications/<notification_id>/read")
@api_auth_required
def notification_read(notification_id: str):
    user = get_request_user()
    row = UserNotification.objects(id=notification_id, recipient=user).first()
    if not row:
        return jsonify({"ok": False, "error": "not_found"}), 404
    if row.read_at is None:
        row.update(set__read_at=utc_now())
    return jsonify({"ok": True})


@bp.post("/notifications/read-all")
@api_auth_required
def notifications_read_all():
    user = get_request_user()
    updated = UserNotification.objects(recipient=user, read_at=None).update(set__read_at=utc_now())
    return jsonify({"ok": True, "updated": int(updated or 0)})


@bp.get("/users/mentionable")
@api_auth_required
def mentionable_users():
    current = get_request_user()
    needle = str(request.args.get("q") or "").strip().lower()[:80]
    pn = str(request.args.get("pn") or "").strip()
    rev = str(request.args.get("rev") or "").strip()
    if not pn:
        return jsonify({"ok": False, "error": "part_required"}), 400
    # Mentioning is a commenting action, so it needs comment authority. This
    # also keeps the internal directory away from customer and supplier portals.
    if not has_permission(current, "comments.write") or uses_portal_presentation(
        current,
        "comments.write",
        resource_type="parts",
    ):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    part = Part.objects(part_number__iexact=pn, revision__iexact=rev).first()
    if not part:
        return jsonify({"ok": False, "error": "part_not_found"}), 404
    if not authorise_part_access(current, part.part_number, part.revision or "").allowed:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    users = []
    for user in User.objects(active=True).order_by("email"):
        if str(user.id) == str(current.id):
            continue
        profile = profile_for_user(user)
        haystack = f"{user.email} {profile.get('label') or ''}".lower()
        if needle and needle not in haystack:
            continue
        # Only suggest people who could actually read the part and reply on it.
        if not has_permission(user, "comments.read"):
            continue
        if not authorise_part_access(user, part.part_number, part.revision or "").allowed:
            continue
        users.append({
            "id": str(user.id),
            "email": user.email,
            "profile": {
                "label": profile.get("label") or user.email,
                "initials": profile.get("initials") or "U",
                "avatar_color": profile.get("avatar_color") or "#1d4ed8",
                "avatar_shape": profile.get("avatar_shape") or "circle",
            },
        })
        if len(users) >= 10:
            break
    return jsonify({"ok": True, "users": users})
