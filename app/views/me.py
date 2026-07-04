from __future__ import annotations

from flask import Blueprint, request, jsonify
from mongoengine.errors import ValidationError

from app.models.auth import User
from app.models.api_token import ApiToken
from app.models.user_settings import UserSettings
from app.services.api_auth import api_auth_required, get_request_user
from app.services.api_tokens import create_token
from app.services.user_settings import get_or_create_settings, settings_to_dict, apply_settings_payload
from app.services.acl import user_has_permission
from app.services.timezone_utils import resolve_timezone_name, utc_now
from app.views.api_helpers import add_datetime_fields, app_timezone_payload

bp = Blueprint("me_api", __name__, url_prefix="/api")


def _role_names(user) -> set[str]:
    names = set()
    for r in (getattr(user, "roles", []) or []):
        if getattr(r, "name", None):
            names.add(str(r.name))
    return names


def _is_admin(user) -> bool:
    if not user:
        return False
    if "admin" in _role_names(user):
        return True
    return user_has_permission(user, "admin")


def _token_dict(token: ApiToken) -> dict:
    payload = {
        "id": str(token.id),
        "label": token.label or "",
    }
    add_datetime_fields(payload, "created_at", token.created_at)
    add_datetime_fields(payload, "last_used_at", token.last_used_at)
    add_datetime_fields(payload, "revoked_at", token.revoked_at)
    add_datetime_fields(payload, "expires_at", token.expires_at)
    return payload


@bp.get("/app/timezone")
def app_timezone():
    payload = app_timezone_payload()
    payload["timezone_display"] = resolve_timezone_name()
    return jsonify(payload)


@bp.get("/me/tokens")
@api_auth_required
def list_tokens():
    user = get_request_user()
    tokens = ApiToken.objects(user_id=user).order_by("-created_at")
    return jsonify({"ok": True, "tokens": [_token_dict(t) for t in tokens]})


@bp.post("/me/tokens")
@api_auth_required
def create_token_api():
    user = get_request_user()
    payload = request.get_json(force=True, silent=True) or {}
    label = str(payload.get("label") or "").strip()
    token_doc, raw = create_token(user, label)
    return jsonify({"ok": True, "token": raw, "token_id": str(token_doc.id), "label": token_doc.label})


@bp.delete("/me/tokens/<token_id>")
@api_auth_required
def revoke_token(token_id: str):
    user = get_request_user()
    token = ApiToken.objects(id=token_id, user_id=user).first()
    if not token:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "Token not found.", "details": []}}), 404
    token.update(set__revoked_at=utc_now())
    return jsonify({"ok": True})


@bp.get("/me/settings")
@api_auth_required
def get_settings():
    user = get_request_user()
    settings = get_or_create_settings(user)
    return jsonify({"ok": True, "settings": settings_to_dict(settings)})


@bp.put("/me/settings")
@api_auth_required
def save_settings():
    user = get_request_user()
    settings = get_or_create_settings(user)
    payload = request.get_json(force=True, silent=True) or {}
    settings = apply_settings_payload(settings, payload)
    return jsonify({"ok": True, "settings": settings_to_dict(settings)})


@bp.get("/admin/users")
@api_auth_required
def list_users():
    user = get_request_user()
    if not _is_admin(user):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    users = User.objects().order_by("email")
    return jsonify({
        "ok": True,
        "users": [{"id": str(u.id), "email": u.email, "roles": [r.name for r in (u.roles or [])]} for u in users],
    })


@bp.get("/admin/users/<user_id>/tokens")
@api_auth_required
def admin_list_tokens(user_id: str):
    user = get_request_user()
    if not _is_admin(user):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    target = User.objects(id=user_id).first()
    if not target:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "User not found.", "details": []}}), 404
    tokens = ApiToken.objects(user_id=target).order_by("-created_at")
    return jsonify({"ok": True, "tokens": [_token_dict(t) for t in tokens]})


@bp.delete("/admin/users/<user_id>/tokens/<token_id>")
@api_auth_required
def admin_revoke_token(user_id: str, token_id: str):
    user = get_request_user()
    if not _is_admin(user):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    token = ApiToken.objects(id=token_id, user_id=user_id).first()
    if not token:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "Token not found.", "details": []}}), 404
    token.update(set__revoked_at=utc_now())
    return jsonify({"ok": True})


@bp.get("/admin/users/<user_id>/settings")
@api_auth_required
def admin_get_settings(user_id: str):
    user = get_request_user()
    if not _is_admin(user):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    target = User.objects(id=user_id).first()
    if not target:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "User not found.", "details": []}}), 404
    settings = get_or_create_settings(target)
    return jsonify({"ok": True, "settings": settings_to_dict(settings)})


@bp.put("/admin/users/<user_id>/settings")
@api_auth_required
def admin_save_settings(user_id: str):
    user = get_request_user()
    if not _is_admin(user):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    target = User.objects(id=user_id).first()
    if not target:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "User not found.", "details": []}}), 404
    settings = get_or_create_settings(target)
    payload = request.get_json(force=True, silent=True) or {}
    settings = apply_settings_payload(settings, payload)
    return jsonify({"ok": True, "settings": settings_to_dict(settings)})
