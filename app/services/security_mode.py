from __future__ import annotations

import os
from typing import Iterable, Tuple
from urllib.parse import urlparse

from flask import current_app, has_app_context, request


_LOCALHOSTS = {"localhost", "127.0.0.1", "::1"}
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def security_mode() -> str:
    if has_app_context():
        val = current_app.config.get("TINYMRP_SECURITY_MODE")
    else:
        val = None
    if not val:
        val = os.getenv("TINYMRP_SECURITY_MODE", "")
    val = str(val or "").strip().lower()
    return "strict" if val == "strict" else "compat"


def is_strict_mode() -> bool:
    return security_mode() == "strict"


def is_safe_method(method: str | None) -> bool:
    return (method or "").upper() in _SAFE_METHODS


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in str(value).split(",") if v.strip()]


def _allowed_origins_raw() -> str:
    if has_app_context():
        raw = current_app.config.get("TINYMRP_ALLOWED_ORIGINS")
    else:
        raw = None
    if not raw:
        raw = os.getenv("TINYMRP_ALLOWED_ORIGINS", "")
    return str(raw or "")


def allowed_origins() -> Tuple[set[str], bool]:
    raw = _allowed_origins_raw()
    origins = set()
    allow_any = False
    for entry in _split_csv(raw):
        low = entry.lower()
        if low in ("*", "all"):
            allow_any = True
            continue
        origins.add(entry)
    return origins, allow_any


def _parse_origin(origin: str | None):
    if not origin:
        return None
    try:
        parsed = urlparse(origin)
    except Exception:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.hostname:
        return None
    return parsed


def _origin_host(origin: str | None) -> str | None:
    parsed = _parse_origin(origin)
    if not parsed:
        return None
    host = parsed.hostname or ""
    return host.lower()


def _origin_scheme(origin: str | None) -> str | None:
    parsed = _parse_origin(origin)
    if not parsed:
        return None
    return (parsed.scheme or "").lower()


def _origin_matches_request(origin: str | None) -> bool:
    if not origin:
        return False
    parsed = _parse_origin(origin)
    if not parsed:
        return False
    try:
        req_host = (request.host or "").split(":", 1)[0].lower()
        req_scheme = (request.scheme or "").lower()
    except Exception:
        return False
    return parsed.hostname.lower() == req_host and parsed.scheme.lower() == req_scheme


def _origin_is_localhost(origin: str | None) -> bool:
    host = _origin_host(origin)
    if not host:
        return False
    return host in _LOCALHOSTS


def _origin_matches_allowed(origin: str | None, allowed: Iterable[str]) -> bool:
    if not origin:
        return False
    return origin in set(allowed or [])


def resolve_cors_origin() -> Tuple[str | None, bool]:
    """Return (allowed_origin, allow_credentials)."""
    origin = request.headers.get("Origin")
    origins, allow_any = allowed_origins()
    allow_credentials = False

    if allow_any:
        # Never allow credentials with wildcard origin.
        return "*", False

    if _origin_matches_allowed(origin, origins):
        allow_credentials = _cors_credentials_allowed(explicit=True)
        return origin, allow_credentials

    if security_mode() == "compat":
        if _origin_matches_request(origin) or _origin_is_localhost(origin):
            allow_credentials = True
            return origin, allow_credentials

    return None, False


def _cors_credentials_allowed(*, explicit: bool) -> bool:
    if explicit:
        # Only allow credentials when an explicit allowlist is set.
        val = os.getenv("TINYMRP_CORS_CREDENTIALS", "")
        return str(val).strip().lower() in ("1", "true", "yes", "on")
    if is_strict_mode():
        return False
    return True


def request_has_token() -> bool:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return True
    if request.headers.get("Authentication-Token"):
        return True
    if request.headers.get("X-Auth-Token"):
        return True
    return False


def extract_token_value() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    token = request.headers.get("Authentication-Token", "").strip()
    if token:
        return token
    return request.headers.get("X-Auth-Token", "").strip()


def is_api_request(path: str | None = None) -> bool:
    p = path or request.path or ""
    return p.startswith("/api")


def session_csrf_allowed() -> bool:
    if is_safe_method(request.method):
        return True
    origin = request.headers.get("Origin")
    if origin:
        if _origin_matches_request(origin):
            return True
        if security_mode() == "compat":
            origins, _ = allowed_origins()
            if _origin_matches_allowed(origin, origins):
                return True
            if _origin_is_localhost(origin):
                return True
        return False
    referer = request.headers.get("Referer")
    if referer:
        if _origin_matches_request(referer):
            return True
        if security_mode() == "compat":
            origins, _ = allowed_origins()
            if _origin_matches_allowed(referer, origins):
                return True
            if _origin_is_localhost(referer):
                return True
        return False
    # No origin or referer -> be lenient in compat mode.
    return security_mode() == "compat"
