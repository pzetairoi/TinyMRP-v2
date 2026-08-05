from __future__ import annotations

import os
import re
from datetime import datetime, tzinfo, UTC
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

from flask import current_app, g, has_app_context, has_request_context

DEFAULT_TIMEZONE = "UTC"
PREFERRED_TIMEZONES = [
    "UTC",
    "Australia/Melbourne",
    "Australia/Sydney",
    "Australia/Perth",
    "Europe/London",
    "Europe/Madrid",
    "America/New_York",
    "America/Los_Angeles",
]
_TZ_OFFSET_RE = re.compile(r"(?:Z|[+-]\d{2}:\d{2}|[+-]\d{4})$", re.IGNORECASE)
_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@lru_cache(maxsize=1)
def _available_timezone_names() -> tuple[str, ...]:
    names: set[str] = set()
    try:
        names.update(available_timezones())
    except Exception:
        pass
    if not names:
        names.update(_windows_timezone_names())
    names.update(PREFERRED_TIMEZONES)
    names.add(DEFAULT_TIMEZONE)
    return tuple(sorted(names))


@lru_cache(maxsize=1)
def _windows_timezone_names() -> tuple[str, ...]:
    names: set[str] = set()
    win_dir = os.environ.get("WINDIR") or r"C:\Windows"
    path = Path(win_dir) / "Globalization" / "Time Zone" / "timezones.xml"
    try:
        from defusedxml import ElementTree as _SafeET

        root = _SafeET.parse(str(path)).getroot()
    except Exception:
        return tuple()
    for zone in root.findall(".//Zone"):
        zone_id = str(zone.attrib.get("ID") or "").strip()
        if zone_id:
            names.add(zone_id)
    return tuple(sorted(names))


def _safe_zoneinfo(name: str | None) -> tzinfo | None:
    text = str(name or "").strip()
    if not text:
        return None
    if text.upper() == "UTC":
        return UTC
    try:
        return ZoneInfo(text)
    except Exception:
        return None


def _normalize_timezone_name(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text if text in _available_timezone_names() else None


def _settings_timezone_name() -> str | None:
    cache_key = "_tinymrp_settings_timezone_name"
    if has_request_context() and hasattr(g, cache_key):
        return getattr(g, cache_key)

    value = None
    try:
        from app.models.app_settings import AppSettings

        settings = AppSettings.objects().order_by("-updated_at").only("timezone").first()
        value = _normalize_timezone_name(getattr(settings, "timezone", None))
    except Exception:
        value = None

    if has_request_context():
        setattr(g, cache_key, value)
    return value


def clear_timezone_cache() -> None:
    if has_request_context():
        for key in ("_tinymrp_settings_timezone_name",):
            try:
                delattr(g, key)
            except Exception:
                pass


def utc_now() -> datetime:
    """
    Return a naive UTC datetime suitable for MongoEngine DateTimeField storage.
    """

    return datetime.now(UTC).replace(tzinfo=None)


def as_utc_naive(value: datetime | None) -> datetime | None:
    """
    Convert aware datetime to UTC and strip tzinfo for DB storage.
    Treat naive datetime as already UTC.
    """

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=None)
    return value.astimezone(UTC).replace(tzinfo=None)


def as_utc_aware(value: datetime | None) -> datetime | None:
    """
    Treat naive datetime as UTC and return aware UTC datetime.
    """

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def utc_iso(value: datetime | None) -> str | None:
    """
    Serialize as ISO-8601 UTC with trailing Z.
    """

    dt = as_utc_aware(value)
    if dt is None:
        return None
    if dt.microsecond:
        return dt.isoformat().replace("+00:00", "Z")
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def resolve_timezone_name() -> str:
    """
    Return selected app timezone from AppSettings.timezone if valid;
    otherwise APP_TIMEZONE / DEFAULT_TIMEZONE / UTC.
    """

    settings_name = _settings_timezone_name()
    if settings_name:
        return settings_name

    candidates: list[str | None] = []
    if has_app_context():
        candidates.extend(
            [
                current_app.config.get("APP_TIMEZONE"),
                current_app.config.get("DEFAULT_TIMEZONE"),
            ]
        )
    candidates.extend(
        [
            os.getenv("APP_TIMEZONE"),
            os.getenv("DEFAULT_TIMEZONE"),
            DEFAULT_TIMEZONE,
        ]
    )
    for candidate in candidates:
        normalized = _normalize_timezone_name(candidate)
        if normalized:
            return normalized
    return DEFAULT_TIMEZONE


def resolve_timezone() -> tzinfo:
    """
    Return ZoneInfo for resolve_timezone_name().
    """

    return _safe_zoneinfo(resolve_timezone_name()) or UTC


def timezone_choices() -> list[str]:
    """
    Return sorted valid IANA timezone names with common zones first.
    """

    names = list(_available_timezone_names())
    preferred = [name for name in PREFERRED_TIMEZONES if name in names]
    remaining = [name for name in names if name not in preferred]
    return preferred + remaining


def to_display_dt(value: datetime | None, tz_name: str | None = None) -> datetime | None:
    """
    Treat DB naive datetime as UTC and convert to selected timezone.
    """

    dt = as_utc_aware(value)
    if dt is None:
        return None
    target = _safe_zoneinfo(tz_name or resolve_timezone_name()) or resolve_timezone()
    return dt.astimezone(target)


def format_display_ts(
    value: datetime | None,
    fmt: str = "%Y-%m-%d %H:%M:%S",
    tz_name: str | None = None,
) -> str:
    """
    Format in selected timezone.
    """

    dt = to_display_dt(value, tz_name=tz_name)
    if dt is None:
        return ""
    try:
        return dt.strftime(fmt)
    except Exception:
        return ""


def local_input_value(value: datetime | None) -> str:
    """
    For datetime-local inputs: convert UTC DB value to selected timezone.
    """

    dt = to_display_dt(value)
    return dt.strftime("%Y-%m-%dT%H:%M") if dt else ""


def local_date_value(value: datetime | None) -> str:
    dt = to_display_dt(value)
    return dt.strftime("%Y-%m-%d") if dt else ""


def parse_user_datetime(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    """
    Parse API/form datetime input using the selected app timezone unless an
    explicit offset is supplied.
    """

    text = str(value or "").strip()
    if not text:
        return None

    explicit_tz = bool(_TZ_OFFSET_RE.search(text))
    try:
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        dt = datetime.fromisoformat(normalized)
    except Exception:
        return None

    if _DATE_ONLY_RE.fullmatch(text):
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999) if end_of_day else dt.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

    if explicit_tz or dt.tzinfo is not None:
        return as_utc_naive(dt)

    local_tz = resolve_timezone()
    return as_utc_naive(dt.replace(tzinfo=local_tz))
