from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.api_auth import api_auth_required, get_request_user
from app.services.acl import user_has_permission
from app.services.authorization import has_any_permission, has_permission
from app.services.canonical_fields import rebuild_all_part_canonical_fields
from app.services.field_config import (
    discover_part_attr_fields,
    ensure_active_part_field_indexes,
    get_field_config,
    reset_field_config,
    save_field_config,
)
from app.services.field_policies import filter_part_field_config
from app.services.part_materialized import rebuild_part_materialized_fields
from app.services.user_settings import get_or_create_settings, settings_to_dict

bp = Blueprint("field_config_api", __name__, url_prefix="/api")


def _can_admin(user) -> bool:
    return has_any_permission(
        user,
        ("system.config.manage", "system.rebuild"),
    )


@bp.get("/field-config")
@api_auth_required
def field_config_get():
    user = get_request_user()
    settings = get_or_create_settings(user)
    config = filter_part_field_config(user, get_field_config())
    visible_ids = {
        str(field.get("id") or "")
        for field in config.get("fields") or []
        if isinstance(field, dict)
    }
    preferences = settings_to_dict(settings).get("field_preferences") or {}
    safe_preferences = {"contexts": {}, "review_columns": {}}
    for name, pref in (preferences.get("contexts") or {}).items():
        if name not in config.get("contexts", {}) or not isinstance(pref, dict):
            continue
        safe_preferences["contexts"][name] = {
            "field_ids": [
                str(field_id)
                for field_id in pref.get("field_ids") or []
                if str(field_id) in visible_ids
            ]
        }
    if user_has_permission(user, "comments.read") or user_has_permission(
        user,
        "markups.read",
    ):
        safe_preferences["review_columns"] = dict(
            preferences.get("review_columns") or {}
        )
    return jsonify(
        {
            "ok": True,
            "config": config,
            "user_preferences": safe_preferences,
            "permissions": {"can_admin": _can_admin(user), "imports": {permission: has_permission(user, permission) for permission in ("imports.preview", "imports.execute_low_risk", "imports.execute_approved", "imports.override_approved")}},
        }
    )


@bp.put("/admin/field-config")
@api_auth_required
def field_config_save():
    user = get_request_user()
    if not has_permission(user, "system.config.manage"):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    payload = request.get_json(force=True, silent=True) or {}
    config = save_field_config(payload)
    rebuild = rebuild_part_materialized_fields(config=config)
    indexes = ensure_active_part_field_indexes(config)
    try:
        from app.views.dashboard import clear_dashboard_cache
        clear_dashboard_cache()
    except Exception:
        pass
    return jsonify({"ok": True, "config": config, "indexes": indexes, "rebuild": rebuild})


@bp.get("/admin/field-config/candidates")
@api_auth_required
def field_config_candidates():
    user = get_request_user()
    if not has_permission(user, "system.config.manage"):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    return jsonify({"ok": True, "candidates": discover_part_attr_fields()})


@bp.post("/admin/field-config/reset")
@api_auth_required
def field_config_reset():
    user = get_request_user()
    if not has_permission(user, "system.config.manage"):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    config = reset_field_config()
    rebuild = rebuild_part_materialized_fields(config=config)
    indexes = ensure_active_part_field_indexes(config)
    try:
        from app.views.dashboard import clear_dashboard_cache
        clear_dashboard_cache()
    except Exception:
        pass
    return jsonify({"ok": True, "config": config, "indexes": indexes, "rebuild": rebuild})


@bp.post("/admin/field-config/rebuild-canonical-fields")
@api_auth_required
def field_config_rebuild_canonical_fields():
    user = get_request_user()
    if not has_permission(user, "system.rebuild"):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    report = rebuild_all_part_canonical_fields()
    try:
        from app.views.dashboard import clear_dashboard_cache
        clear_dashboard_cache()
    except Exception:
        pass
    return jsonify({"ok": True, "report": report, "config": get_field_config()})


@bp.post("/admin/field-config/rebuild-search-fields")
@api_auth_required
def field_config_rebuild_search_fields():
    user = get_request_user()
    if not has_permission(user, "system.rebuild"):
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Not authorized.", "details": []}}), 403
    report = rebuild_part_materialized_fields()
    try:
        from app.views.dashboard import clear_dashboard_cache
        clear_dashboard_cache()
    except Exception:
        pass
    config = get_field_config()
    indexes = ensure_active_part_field_indexes(config)
    return jsonify({"ok": True, "report": report, "config": config, "indexes": indexes})
