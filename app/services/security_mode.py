from __future__ import annotations

import os
from typing import Iterable, Tuple
from urllib.parse import urlparse

from flask import current_app, has_app_context, request


_LOCALHOSTS = {"localhost", "127.0.0.1", "::1"}
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

API_AUTH_HEALTH = "health"
API_AUTH_PUBLIC_SHARE = "public_share"
API_AUTH_SESSION = "session"
API_AUTH_BEARER = "bearer"
API_AUTH_SESSION_OR_BEARER = "session_or_bearer"

# Liveness and readiness must answer before any credential exists - an
# orchestrator polls them to decide whether the instance is usable at all.
# Both report booleans and coarse figures only, never configuration values.
_HEALTH_ENDPOINTS = frozenset({"api_health.health", "api_health.ready"})
_PUBLIC_SHARE_ENDPOINTS = frozenset(
    {
        "part_shares.public_share_field_config",
        "part_shares.public_share_part_detail",
        "part_shares.public_share_files_overview",
        "part_shares.public_share_part_images",
        "part_shares.public_share_bom_tree",
        "part_shares.public_share_bom_flat",
        "part_shares.public_share_docpack_options",
        "part_shares.public_share_docpack_build",
        "part_shares.public_share_process_meta",
    }
)


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

    return None, False


def _cors_credentials_allowed(*, explicit: bool) -> bool:
    """Credentials are only ever allowed against an explicit allowlist.

    There used to be a second answer here for compat mode, which returned True
    for anything that had not matched an allowlist. There is one auth model
    now, so an origin that was not explicitly allowed gets no credentials.
    """
    if not explicit:
        return False
    val = os.getenv("TINYMRP_CORS_CREDENTIALS", "")
    return str(val).strip().lower() in ("1", "true", "yes", "on")


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


def api_auth_policy() -> str:
    """Classify the matched API endpoint into its explicit auth category."""
    endpoint = request.endpoint or ""
    if endpoint in _HEALTH_ENDPOINTS:
        return API_AUTH_HEALTH
    if endpoint in _PUBLIC_SHARE_ENDPOINTS:
        return API_AUTH_PUBLIC_SHARE

    view = current_app.view_functions.get(endpoint)
    configured = getattr(view, "_tinymrp_api_auth_policy", None)
    if configured in {API_AUTH_BEARER, API_AUTH_SESSION_OR_BEARER}:
        return configured

    # All other /api routes are browser/session APIs. This fail-closed default
    # prevents a newly added endpoint from becoming anonymously reachable.
    return API_AUTH_SESSION


def session_csrf_allowed() -> bool:
    """Origin/referer check for unsafe methods on SESSION-authenticated requests.

    API-token clients never reach this: app/__init__.py returns early for them,
    which is why retiring the old compat behaviour here could not affect the
    SolidWorks add-in. It authenticates with a token, not a session cookie.

    A request carrying neither Origin nor Referer fails. That used to be
    allowed in compat mode, and it was the loosest rule in the system.
    """
    if is_safe_method(request.method):
        return True
    origin = request.headers.get("Origin")
    if origin:
        return _origin_matches_request(origin)
    referer = request.headers.get("Referer")
    if referer:
        return _origin_matches_request(referer)
    return False
