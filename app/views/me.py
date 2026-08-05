from __future__ import annotations

from flask import Blueprint, request, jsonify
from mongoengine.errors import ValidationError

from app.models.auth import User
from app.models.api_token import ApiToken
from app.services.audit import log_action
from app.services.api_auth import api_auth_required, get_request_user
from app.services.api_tokens import (
    TokenPolicyError,
    create_token,
    revoke_all_tokens,
    revoke_token as revoke_token_document,
    rotate_token as rotate_token_document,
    token_policy,
    token_status,
)
from app.services.authorization import has_permission
from app.services.user_settings import get_or_create_settings, settings_to_dict, apply_settings_payload
from app.services.timezone_utils import resolve_timezone_name
from app.views.api_helpers import add_datetime_fields, app_timezone_payload

bp = Blueprint("me_api", __name__, url_prefix="/api")


def _token_dict(token: ApiToken) -> dict:
    status = token_status(token)
    payload = {
        "id": str(token.id),
        "label": token.label or "",
        "status": status,
        "is_active": status in {"active", "legacy_no_expiry"},
        "legacy_no_expiry": status == "legacy_no_expiry",
        "revocation_reason": token.revocation_reason or "",
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
    return jsonify({
        "ok": True,
        "tokens": [_token_dict(t) for t in tokens],
        "policy": token_policy(),
    })


@bp.post("/me/tokens")
@api_auth_required
def create_token_api():
    user = get_request_user()
    payload = request.get_json(force=True, silent=True) or {}
    label = str(payload.get("label") or "").strip()
    try:
        token_doc, raw = create_token(
            user,
            label,
            lifetime_days=payload.get("expires_in_days"),
        )
    except TokenPolicyError as exc:
        return jsonify({
            "ok": False,
            "error": {
                "code": "invalid_token_policy",
                "message": str(exc),
                "details": [],
            },
        }), 400
    log_action(
        "api_token.create",
        resource_type="api_token",
        resource=str(token_doc.id),
        meta={
            "expires_at": token_doc.expires_at.isoformat()
            if token_doc.expires_at
            else None
        },
    )
    return jsonify({
        "ok": True,
        "token": raw,
        "token_id": str(token_doc.id),
        "label": token_doc.label,
        "token_details": _token_dict(token_doc),
    })


@bp.delete("/me/tokens/<token_id>")
@api_auth_required
def revoke_token(token_id: str):
    user = get_request_user()
    try:
        token = ApiToken.objects(id=token_id, user_id=user).first()
    except ValidationError:
        token = None
    if not token:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "Token not found.", "details": []}}), 404
    changed = revoke_token_document(token, reason="user_revoked")
    log_action(
        "api_token.revoke",
        resource_type="api_token",
        resource=str(token.id),
        meta={"changed": changed},
    )
    return jsonify({"ok": True, "changed": changed})


@bp.post("/me/tokens/<token_id>/rotate")
@api_auth_required
def rotate_token(token_id: str):
    user = get_request_user()
    try:
        token = ApiToken.objects(id=token_id, user_id=user).first()
    except ValidationError:
        token = None
    if not token:
        return jsonify({
            "ok": False,
            "error": {
                "code": "not_found",
                "message": "Token not found.",
                "details": [],
            },
        }), 404
    payload = request.get_json(force=True, silent=True) or {}
    try:
        replacement, raw = rotate_token_document(
            token,
            user,
            lifetime_days=payload.get("expires_in_days"),
        )
    except TokenPolicyError as exc:
        return jsonify({
            "ok": False,
            "error": {
                "code": "invalid_token_policy",
                "message": str(exc),
                "details": [],
            },
        }), 400
    log_action(
        "api_token.rotate",
        resource_type="api_token",
        resource=str(token.id),
        meta={"replacement_token_id": str(replacement.id)},
    )
    return jsonify({
        "ok": True,
        "token": raw,
        "token_id": str(replacement.id),
        "replaced_token_id": str(token.id),
        "label": replacement.label,
        "token_details": _token_dict(replacement),
    })


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
    if not has_permission(user, "security.users.read"):
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
    if not has_permission(user, "security.tokens.revoke"):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    target = User.objects(id=user_id).first()
    if not target:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "User not found.", "details": []}}), 404
    tokens = ApiToken.objects(user_id=target).order_by("-created_at")
    return jsonify({
        "ok": True,
        "tokens": [_token_dict(t) for t in tokens],
        "policy": token_policy(),
    })


@bp.delete("/admin/users/<user_id>/tokens/<token_id>")
@api_auth_required
def admin_revoke_token(user_id: str, token_id: str):
    user = get_request_user()
    if not has_permission(user, "security.tokens.revoke"):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    try:
        token = ApiToken.objects(id=token_id, user_id=user_id).first()
    except ValidationError:
        token = None
    if not token:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "Token not found.", "details": []}}), 404
    changed = revoke_token_document(token, reason="administrator_revoked")
    log_action(
        "api_token.admin_revoke",
        resource_type="api_token",
        resource=str(token.id),
        meta={"target_user_id": user_id, "changed": changed},
    )
    return jsonify({"ok": True, "changed": changed})


@bp.post("/admin/tokens/revoke-all")
@api_auth_required
def admin_revoke_all_tokens():
    user = get_request_user()
    if not has_permission(user, "security.tokens.revoke"):
        return jsonify({
            "ok": False,
            "error": {
                "code": "forbidden",
                "message": "Not authorized.",
                "details": [],
            },
        }), 403
    revoked_count = revoke_all_tokens()
    log_action(
        "api_token.admin_revoke_all",
        resource_type="api_token",
        resource="all",
        meta={"revoked_count": revoked_count},
    )
    return jsonify({"ok": True, "revoked_count": revoked_count})


@bp.get("/admin/users/<user_id>/settings")
@api_auth_required
def admin_get_settings(user_id: str):
    user = get_request_user()
    if not has_permission(user, "security.users.manage"):
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
    if not has_permission(user, "security.users.manage"):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    target = User.objects(id=user_id).first()
    if not target:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "User not found.", "details": []}}), 404
    settings = get_or_create_settings(target)
    payload = request.get_json(force=True, silent=True) or {}
    settings = apply_settings_payload(settings, payload)
    return jsonify({"ok": True, "settings": settings_to_dict(settings)})
