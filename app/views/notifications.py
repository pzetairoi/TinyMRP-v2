from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.models.auth import User
from app.models.notification import UserNotification
from app.models.part import Part
from app.services.acl import allowed_parts_for, part_is_allowed
from app.services.api_auth import api_auth_required, get_request_user
from app.services.timezone_utils import utc_iso, utc_now
from app.services.user_profile import profile_for_user


bp = Blueprint("notifications_api", __name__, url_prefix="/api")


def _payload(row: UserNotification) -> dict:
    return {
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


@bp.get("/notifications")
@api_auth_required
def notifications_list():
    user = get_request_user()
    try:
        limit = max(1, min(100, int(request.args.get("limit") or 20)))
    except (TypeError, ValueError):
        limit = 20
    query = UserNotification.objects(recipient=user)
    if str(request.args.get("unread_only") or "").lower() in ("1", "true", "yes"):
        query = query.filter(read_at=None)
    rows = list(query.order_by("-created_at")[:limit])
    unread_count = UserNotification.objects(recipient=user, read_at=None).count()
    return jsonify({"ok": True, "unread_count": unread_count, "notifications": [_payload(row) for row in rows]})


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
    part = Part.objects(part_number__iexact=pn, revision__iexact=rev).first()
    if not part:
        return jsonify({"ok": False, "error": "part_not_found"}), 404
    try:
        current_allowed = allowed_parts_for(current)
        if isinstance(current_allowed, set) and not part_is_allowed(current_allowed, part.part_number, part.revision or ""):
            return jsonify({"ok": False, "error": "forbidden"}), 403
    except Exception:
        pass
    users = []
    for user in User.objects(active=True).order_by("email"):
        if str(user.id) == str(current.id):
            continue
        profile = profile_for_user(user)
        haystack = f"{user.email} {profile.get('label') or ''}".lower()
        if needle and needle not in haystack:
            continue
        try:
            target_allowed = allowed_parts_for(user)
            if isinstance(target_allowed, set) and not part_is_allowed(target_allowed, part.part_number, part.revision or ""):
                continue
        except Exception:
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
