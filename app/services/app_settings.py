from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context

from app.models.app_settings import AppSettings

_DEFAULT_TIMEZONE = "UTC"
_FILE_SOURCE_ID_RE = re.compile(r"[^a-z0-9]+")


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


def _clean_source_id(value: str, fallback: str) -> str:
    text = _FILE_SOURCE_ID_RE.sub("-", str(value or "").strip().lower()).strip("-")
    return text or fallback


def normalize_file_sources(
    raw_sources: List[Dict[str, Any]] | None,
    *,
    fallback_root: str = "",
    fallback_url: str = "",
) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for idx, raw in enumerate(raw_sources or []):
        if not isinstance(raw, dict):
            continue
        local_root = str(raw.get("local_root") or "").strip()
        if not local_root:
            continue
        priority_raw = raw.get("priority")
        try:
            priority = max(1, int(priority_raw))
        except Exception:
            priority = idx + 1
        source_id = _clean_source_id(
            str(raw.get("id") or raw.get("label") or f"source-{idx + 1}"),
            f"source-{idx + 1}",
        )
        while source_id in seen_ids:
            source_id = f"{source_id}-{idx + 1}"
        seen_ids.add(source_id)
        use_for_approved = bool(raw.get("use_for_approved", True))
        use_for_unapproved = bool(raw.get("use_for_unapproved", True))
        if not use_for_approved and not use_for_unapproved:
            use_for_approved = True
            use_for_unapproved = True
        sources.append(
            {
                "id": source_id,
                "label": str(raw.get("label") or source_id).strip() or source_id,
                "local_root": local_root.rstrip("/\\"),
                "url_prefix": str(raw.get("url_prefix") or "").strip().rstrip("/"),
                "priority": priority,
                "use_for_approved": use_for_approved,
                "use_for_unapproved": use_for_unapproved,
                "active": bool(raw.get("active", True)),
            }
        )

    if not sources and fallback_root:
        sources.append(
            {
                "id": "primary",
                "label": "Primary",
                "local_root": fallback_root.rstrip("/\\"),
                "url_prefix": fallback_url.rstrip("/"),
                "priority": 1,
                "use_for_approved": True,
                "use_for_unapproved": True,
                "active": True,
            }
        )

    sources.sort(key=lambda item: (int(item.get("priority") or 0), str(item.get("label") or "")))
    return sources


def resolve_file_sources(
    settings: Optional[AppSettings] = None,
    *,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    settings = settings or get_app_settings(create=False)
    cfg = config or (current_app.config if has_app_context() else {})
    fallback_root = (cfg.get("FILES_LOCAL_ROOT") or cfg.get("FILE_ROOT_LOCAL") or "").strip()
    fallback_url = (cfg.get("FILES_URL_PREFIX") or cfg.get("FILE_ROOT_HTTP") or "").strip()
    raw_sources = getattr(settings, "file_sources", None) if settings else None
    return normalize_file_sources(raw_sources or [], fallback_root=fallback_root, fallback_url=fallback_url)


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
