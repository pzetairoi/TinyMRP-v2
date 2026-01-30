from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from flask import current_app

from app.models.app_settings import AppSettings

_DEFAULT_TIMEZONE = "UTC"


def get_app_settings(create: bool = True) -> Optional[AppSettings]:
    settings = AppSettings.objects().order_by("-updated_at").first()
    if settings or not create:
        return settings
    settings = AppSettings()
    settings.save()
    return settings


def branding_root() -> Tuple[str, str]:
    base = (current_app.config.get("FILE_ROOT_LOCAL") or "").strip()
    if not base:
        base = current_app.instance_path
    path = os.path.join(base, "_branding")
    os.makedirs(path, exist_ok=True)
    return path, base


def _safe_zoneinfo(name: str | None) -> Optional[ZoneInfo]:
    name = (name or "").strip()
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except Exception:
        return None


def _system_timezone_name() -> str:
    try:
        tzinfo = datetime.now().astimezone().tzinfo
        return getattr(tzinfo, "key", "") or ""
    except Exception:
        return ""


def resolve_timezone() -> ZoneInfo:
    settings = get_app_settings(create=False)
    if settings and settings.timezone:
        tz = _safe_zoneinfo(settings.timezone)
        if tz:
            return tz

    cfg = (
        current_app.config.get("DEFAULT_TIMEZONE")
        or os.getenv("APP_TIMEZONE")
        or os.getenv("TZ")
        or ""
    )
    tz = _safe_zoneinfo(cfg)
    if tz:
        return tz

    sys_name = _system_timezone_name()
    tz = _safe_zoneinfo(sys_name)
    if tz:
        return tz
    tz = _safe_zoneinfo(_DEFAULT_TIMEZONE)
    if tz:
        return tz
    return timezone.utc


def get_display_dt(build_ts: Optional[datetime] = None) -> datetime:
    tz = resolve_timezone()
    if build_ts is None:
        return datetime.now(tz)
    if build_ts.tzinfo is None:
        local_tz = _safe_zoneinfo(_system_timezone_name()) or _safe_zoneinfo(_DEFAULT_TIMEZONE) or timezone.utc
        build_ts = build_ts.replace(tzinfo=local_tz)
    return build_ts.astimezone(tz)


def format_display_ts(build_ts: Optional[datetime] = None) -> str:
    try:
        return get_display_dt(build_ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def resolve_brand_logo_path() -> Optional[str]:
    settings = get_app_settings(create=False)
    rel_path = (settings.brand_logo_rel_path if settings else "") or ""
    rel_path = rel_path.strip()
    if not rel_path:
        return None
    if os.path.isabs(rel_path):
        return rel_path if os.path.isfile(rel_path) else None
    _, base = branding_root()
    abs_path = os.path.normpath(os.path.join(base, rel_path))
    try:
        if os.path.commonpath([abs_path, os.path.normpath(base)]) != os.path.normpath(base):
            return None
    except Exception:
        return None
    return abs_path if os.path.isfile(abs_path) else None
