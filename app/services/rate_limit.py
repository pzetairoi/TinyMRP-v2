"""Rate limiting (Phase 1).

Applies request throttling to authentication endpoints and, optionally, a global
API budget. Uses Flask-Limiter with in-memory storage by default; point
RATE_LIMIT_STORAGE_URI at Redis (e.g. redis://redis:6379/0) for multi-worker or
multi-instance deployments so all workers share one budget.

Environment / config:
- RATE_LIMIT_ENABLED       default "true"; "false" disables everything.
- RATE_LIMIT_STORAGE_URI   default "memory://".
- RATE_LIMIT_LOGIN         default "10 per minute;100 per hour" (login + password endpoints).
- RATE_LIMIT_API           optional global budget for /api/* per client address
                           (e.g. "600 per minute"). Empty/unset = no global API limit.
- RATE_LIMIT_EXPENSIVE     overrides the per-route budget for every expensive
                           endpoint at once (e.g. "20 per hour").
"""

from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, request

logger = logging.getLogger(__name__)

# Endpoints whose cost is measured in seconds and disk I/O rather than
# milliseconds: building document packs, importing a pack, and exports. A
# global /api budget does not protect these - a handful of concurrent docpack
# builds can saturate the box while staying well inside any per-minute API
# allowance. Each entry is (endpoint, default limit); the limit is overridable
# with RATE_LIMIT_EXPENSIVE.
# Budgets are deliberately GENEROUS. These are authenticated users doing real
# work, so the threat is a runaway client or a pathological pack, not fraud.
# Breaking a legitimate import session is worse than the abuse a tight limit
# would prevent.
_EXPENSIVE_ENDPOINTS = (
    ("docpacks_api.build_order", "30 per hour"),
    ("part_shares.public_share_docpack_build", "30 per hour"),
    ("upload_pack_api.upload_pack", "60 per hour"),
    ("upload_pack_api.upload_extra_files", "60 per hour"),
    ("tools.excel_compile", "60 per hour"),
    ("tools.excel_compile_download", "60 per hour"),
)

_AUTH_ENDPOINTS = (
    "security.login",
    "security.change_password",
    "security.forgot_password",
    "security.reset_password",
    "security.two_factor_token_validation",
)


def _truthy(value: str | None, default: bool = True) -> bool:
    if value is None or not str(value).strip():
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _expensive_key() -> str:
    """Budget the expensive routes per USER, not per client address.

    A whole company normally reaches the server from one public IP, so an
    address-keyed budget would be shared by everyone in the office - which
    turns a generous limit into a tight one for exactly the people doing real
    work. Falls back to the address for the unauthenticated public-share
    docpack route, where there is no user to key on.
    """
    from flask_limiter.util import get_remote_address

    try:
        from flask_login import current_user

        if getattr(current_user, "is_authenticated", False):
            return f"user:{current_user.get_id()}"
    except Exception:
        pass
    return f"addr:{get_remote_address()}"


def init_rate_limiting(app: Flask):
    """Attach a Limiter to the app. Returns the limiter (or None when disabled)."""
    enabled = _truthy(os.getenv("RATE_LIMIT_ENABLED"), default=True)
    app.config.setdefault("RATE_LIMIT_ENABLED", enabled)
    if not enabled:
        logger.info("Rate limiting disabled via RATE_LIMIT_ENABLED")
        return None

    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
    except Exception:  # pragma: no cover - dependency missing
        logger.warning("Flask-Limiter not installed; rate limiting is OFF")
        return None

    storage_uri = (os.getenv("RATE_LIMIT_STORAGE_URI") or "memory://").strip()
    login_limit = (os.getenv("RATE_LIMIT_LOGIN") or "10 per minute;100 per hour").strip()
    api_limit = (os.getenv("RATE_LIMIT_API") or "").strip()

    # OPS-RATE-01. Two distinct problems live here.
    #
    # 1. memory:// storage is PER WORKER. gunicorn runs 2 workers by default, so
    #    a "10 per minute" login limit is really 20 attempts per minute against
    #    the deployment. Redis makes the budget genuinely shared.
    # 2. Storage-failure policy must be an explicit decision, not an accident.
    #    swallow_errors=True means a Redis outage silently disables limiting
    #    (fail-open). That is the right default for the whole app - losing rate
    #    limiting is far better than refusing all traffic - but it is a real
    #    security downgrade during an outage and it was previously unrecorded.
    #    RATE_LIMIT_FAIL_CLOSED=true inverts it for deployments that would
    #    rather reject requests than serve them unthrottled.
    fail_closed = _truthy(os.getenv("RATE_LIMIT_FAIL_CLOSED"), default=False)
    using_shared_storage = not storage_uri.startswith("memory:")

    app.config["RATE_LIMIT_STORAGE_URI"] = storage_uri
    app.config["RATE_LIMIT_SHARED_STORAGE"] = using_shared_storage
    app.config["RATE_LIMIT_FAIL_CLOSED"] = fail_closed

    if not using_shared_storage:
        logger.warning(
            "Rate limiting uses per-worker memory storage, so configured limits "
            "are multiplied by the worker count. Set RATE_LIMIT_STORAGE_URI to a "
            "shared store (e.g. redis://redis:6379/0) for a real budget."
        )

    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=storage_uri,
        headers_enabled=True,
        # swallow_errors=True -> a storage outage degrades to no limiting
        # (fail-open). False -> the storage error propagates and the request
        # fails (fail-closed).
        swallow_errors=not fail_closed,
        default_limits=[api_limit] if api_limit else [],
    )

    if api_limit:
        # Default limits act as the global /api budget: everything else is filtered out.
        @limiter.request_filter
        def _non_api_exempt() -> bool:
            path = (request.path or "").rstrip("/")
            if not path.startswith("/api"):
                return True
            # Liveness and readiness are polled continuously by container
            # healthchecks and load balancers; rate-limiting them would make an
            # instance look unhealthy purely because it was being monitored.
            return path in ("/api/health", "/api/ready")

    limiter.init_app(app)
    app.extensions["tinymrp_limiter"] = limiter

    # Throttle authentication endpoints registered by Flask-Security.
    for endpoint in _AUTH_ENDPOINTS:
        view = app.view_functions.get(endpoint)
        if view is not None:
            app.view_functions[endpoint] = limiter.limit(
                login_limit, error_message="Too many attempts. Try again later."
            )(view)

    # Expensive-route budgets cannot be applied here: this runs long before the
    # blueprints are registered, so app.view_functions is still empty for them.
    # create_app calls apply_expensive_limits() once the routes exist.

    # 429 responses as JSON for API paths, friendly text otherwise. Audit-logged.
    @app.errorhandler(429)
    def _rate_limited(e):
        try:
            from app.services.audit import log_action

            log_action(
                "security.rate_limited",
                resource_type="request",
                resource=request.path,
                meta={"remote": get_remote_address(), "limit": str(getattr(e, "description", ""))},
            )
        except Exception:
            pass
        logger.warning("rate limited: %s %s", request.method, request.path)
        if (request.path or "").startswith("/api/") or request.accept_mimetypes.best == "application/json":
            return (
                jsonify({"ok": False, "error": "rate_limited", "detail": str(getattr(e, "description", ""))}),
                429,
            )
        return ("Too many requests. Please slow down and try again shortly.", 429)

    logger.info("Rate limiting enabled (storage=%s, login=%s, api=%s)", storage_uri, login_limit, api_limit or "off")
    return limiter


def apply_expensive_limits(app: Flask) -> list[str]:
    """Throttle the expensive routes. Call AFTER every blueprint is registered.

    Separate from init_rate_limiting on purpose, and this is the whole reason
    the first attempt failed: rate limiting is initialised early in create_app,
    hundreds of lines before the blueprints exist, so the lookup found nothing
    and skipped all six routes in silence. The endpoint names were correct -
    they were simply asked for too early. The existing name-resolution test did
    not catch it because it inspects the FINISHED app, by which time every
    route is present.

    Returns the endpoints actually throttled so a caller (and the tests) can
    tell enforcement from a silent skip.
    """
    limiter = app.extensions.get("tinymrp_limiter")
    if limiter is None:
        return []

    override = (os.getenv("RATE_LIMIT_EXPENSIVE") or "").strip()
    applied: list[str] = []
    for endpoint, default_limit in _EXPENSIVE_ENDPOINTS:
        view = app.view_functions.get(endpoint)
        if view is None:
            # A rename must not break startup, but it must not pass unnoticed
            # either: an unthrottled expensive route is the failure this whole
            # item exists to prevent.
            logger.warning("rate limit skipped: endpoint %s not registered", endpoint)
            continue
        app.view_functions[endpoint] = limiter.limit(
            override or default_limit,
            key_func=_expensive_key,
            error_message="This operation is temporarily rate limited. Try again shortly.",
        )(view)
        applied.append(endpoint)
    return applied
