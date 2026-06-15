from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.api_auth import api_auth_required, get_request_user
from app.services.acl import user_has_permission
from app.services.field_config import discover_part_attr_fields, get_field_config, reset_field_config, save_field_config
from app.services.user_settings import get_or_create_settings, settings_to_dict

bp = Blueprint("field_config_api", __name__, url_prefix="/api")


def _role_names(user) -> set[str]:
    names = set()
    for role in (getattr(user, "roles", []) or []):
        name = getattr(role, "name", None)
        if name:
            names.add(str(name))
    return names


def _is_admin(user) -> bool:
    if not user:
        return False
    if "admin" in _role_names(user):
        return True
    return user_has_permission(user, "admin")


@bp.get("/field-config")
@api_auth_required
def field_config_get():
    user = get_request_user()
    settings = get_or_create_settings(user)
    config = get_field_config()
    return jsonify(
        {
            "ok": True,
            "config": config,
            "user_preferences": settings_to_dict(settings).get("field_preferences") or {},
            "permissions": {"can_admin": _is_admin(user)},
        }
    )


@bp.put("/admin/field-config")
@api_auth_required
def field_config_save():
    user = get_request_user()
    if not _is_admin(user):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    payload = request.get_json(force=True, silent=True) or {}
    config = save_field_config(payload)
    return jsonify({"ok": True, "config": config})


@bp.get("/admin/field-config/candidates")
@api_auth_required
def field_config_candidates():
    user = get_request_user()
    if not _is_admin(user):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    return jsonify({"ok": True, "candidates": discover_part_attr_fields()})


@bp.post("/admin/field-config/reset")
@api_auth_required
def field_config_reset():
    user = get_request_user()
    if not _is_admin(user):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    config = reset_field_config()
    return jsonify({"ok": True, "config": config})
