from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, g, has_app_context, has_request_context

from app.models.app_settings import AppSettings
from app.services.timezone_utils import (
    format_display_ts as _format_display_ts,
    to_display_dt,
    utc_now,
)

_DEFAULT_TIMEZONE = "UTC"
_FILE_SOURCE_ID_RE = re.compile(r"[^a-z0-9]+")


def get_app_settings(create: bool = True) -> Optional[AppSettings]:
    """The single AppSettings document, memoised FOR THE CURRENT REQUEST.

    This is called from many small helpers, so it was re-read constantly: the
    profiler measured app_settings twice on every request and 593 times in one
    docpacks/build. It is one document that does not change during a request,
    and re-reading it is pure overhead paid even by the cheapest call.

    Request-scoped rather than cached globally, on purpose. An administrator
    changing a setting must see it take effect on the next request, not after
    a restart or an eviction. Outside a request context nothing is memoised,
    so CLI commands and imports always read fresh.
    """
    if has_request_context():
        cached = g.get("_tinymrp_app_settings", None) if hasattr(g, "get") else None
        if cached is not None:
            return cached

    settings = AppSettings.objects().order_by("-updated_at").first()
    if not settings and create:
        settings = AppSettings()
        settings.save()

    if settings is not None and has_request_context():
        g._tinymrp_app_settings = settings
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

def get_display_dt(build_ts: Optional[datetime] = None) -> datetime:
    return to_display_dt(build_ts or utc_now())


def format_display_ts(
    build_ts: Optional[datetime] = None,
    fmt: str = "%Y-%m-%d %H:%M",
) -> str:
    try:
        return _format_display_ts(build_ts, fmt=fmt)
    except Exception:
        return ""


def permission_test_data_enabled() -> bool:
    """Whether the permission-test environment is available on this instance.

    Reads the dashboard setting first and falls back to the
    ALLOW_PERMISSION_TEST_DATA environment variable when no administrator has
    ever touched the toggle. That ordering is what lets the flag be changed
    without editing a config file and restarting, while leaving instances that
    already set it in their .env behaving exactly as before.

    Never raises: a database that is unreachable must not turn a permission
    check into a 500. It falls back to the environment, which is the value the
    instance booted with.
    """
    try:
        settings = get_app_settings(create=False)
        if settings is not None:
            stored = settings.allow_permission_test_data
            if stored is not None:
                return bool(stored)
    except Exception:
        pass

    if has_app_context():
        return bool(current_app.config.get("ALLOW_PERMISSION_TEST_DATA", False))
    return False


def set_permission_test_data_enabled(enabled: Optional[bool]) -> None:
    """Set the toggle. None clears it back to following the environment."""
    settings = get_app_settings(create=True)
    if settings is None:
        return
    settings.allow_permission_test_data = None if enabled is None else bool(enabled)
    settings.updated_at = utc_now()
    settings.save()
    if has_request_context():
        g._tinymrp_app_settings = settings


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
