from __future__ import annotations

from typing import Dict, Any

from app.models.user_settings import UserSettings
from app.services.field_config import sanitize_user_field_preferences
from app.services.numbering_presets import get_recommended_scheme
from app.services.user_profile import default_profile_settings, sanitize_profile
from app.services.timezone_utils import utc_iso, utc_now


DEFAULT_PROPERTY_MAP = {
    "part_number_prop": "PartNumber",
    "revision_prop": "Revision",
    "display_code_prop": "DisplayCode",
}


def default_settings_dict() -> Dict[str, Any]:
    scheme = get_recommended_scheme()
    scheme_id = str(scheme.id) if scheme else ""
    return {
        "default_scheme_id": scheme_id,
        "default_context": {},
        "sw_property_map": dict(DEFAULT_PROPERTY_MAP),
        "apply_mode": "active_config",
        "profile": default_profile_settings(),
        "ui_preferences": {"show_advanced": False},
        "field_preferences": {},
        "updated_at": utc_now(),
    }


def get_or_create_settings(user) -> UserSettings:
    settings = UserSettings.objects(user_id=user).first()
    if settings:
        return settings
    defaults = default_settings_dict()
    settings = UserSettings(user_id=user, **defaults)
    settings.save()
    return settings


def settings_to_dict(settings: UserSettings) -> Dict[str, Any]:
    field_preferences = sanitize_user_field_preferences(settings.field_preferences or {})
    return {
        "id": str(settings.id),
        "default_scheme_id": settings.default_scheme_id or "",
        "default_context": settings.default_context or {},
        "sw_property_map": settings.sw_property_map or dict(DEFAULT_PROPERTY_MAP),
        "apply_mode": settings.apply_mode or "active_config",
        "profile": sanitize_profile(settings.profile or {}),
        "ui_preferences": settings.ui_preferences or {"show_advanced": False},
        "field_preferences": field_preferences,
        "updated_at": utc_iso(settings.updated_at),
    }


def apply_settings_payload(settings: UserSettings, payload: Dict[str, Any]) -> UserSettings:
    if "default_scheme_id" in payload:
        settings.default_scheme_id = str(payload.get("default_scheme_id") or "").strip()
    if "default_context" in payload and isinstance(payload.get("default_context"), dict):
        settings.default_context = payload.get("default_context") or {}
    if "sw_property_map" in payload and isinstance(payload.get("sw_property_map"), dict):
        settings.sw_property_map = payload.get("sw_property_map") or dict(DEFAULT_PROPERTY_MAP)
    if "apply_mode" in payload:
        settings.apply_mode = str(payload.get("apply_mode") or "active_config")
    if "profile" in payload and isinstance(payload.get("profile"), dict):
        settings.profile = sanitize_profile(payload.get("profile") or {})
    if "ui_preferences" in payload and isinstance(payload.get("ui_preferences"), dict):
        settings.ui_preferences = payload.get("ui_preferences") or {}
    if "field_preferences" in payload and isinstance(payload.get("field_preferences"), dict):
        settings.field_preferences = sanitize_user_field_preferences(payload.get("field_preferences") or {})

    settings.updated_at = utc_now()
    settings.save()
    return settings
