from __future__ import annotations

from datetime import datetime
from functools import wraps
from typing import Optional, Tuple

from flask import g, jsonify
from flask_security import current_user

from app.models.auth import User
from app.services.api_tokens import verify_token, touch_last_used
from app.services.security_mode import (
    API_AUTH_BEARER,
    API_AUTH_SESSION_OR_BEARER,
    extract_token_value,
)


def api_error_response(
    code: str,
    message: str,
    *,
    status: int = 401,
    details: list[str] | None = None,
):
    """Return the common JSON error envelope used by authentication guards."""
    return jsonify(
        {
            "ok": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
            },
        }
    ), status


def _user_from_token(raw_token: str) -> Tuple[Optional[User], Optional[str]]:
    token = verify_token(raw_token)
    if not token:
        return None, None
    touch_last_used(token)
    return token.user_id, str(token.id)


def get_request_user() -> Optional[User]:
    user = getattr(g, "api_user", None)
    if user:
        return user
    if getattr(current_user, "is_authenticated", False):
        return current_user
    return None


def _token_error(code: str):
    messages = {
        "token_required": "A valid API bearer token is required.",
        "invalid_token": "The API bearer token is invalid, expired, or revoked.",
    }
    return api_error_response(code, messages.get(code, "Authentication failed."))


def authenticate_api_token():
    user = getattr(g, "api_user", None)
    if user:
        return user, None

    token_value = extract_token_value()
    if not token_value:
        return None, _token_error("token_required")

    user, token_id = _user_from_token(token_value)
    if not user:
        return None, _token_error("invalid_token")

    g.api_user = user
    g.api_token_id = token_id
    return user, None


def api_auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if getattr(g, "api_user", None):
            return fn(*args, **kwargs)

        token_value = extract_token_value()
        if token_value:
            user, token_id = _user_from_token(token_value)
            if not user:
                return _token_error("invalid_token")
            g.api_user = user
            g.api_token_id = token_id
            return fn(*args, **kwargs)

        if getattr(current_user, "is_authenticated", False):
            return fn(*args, **kwargs)

        return api_error_response("authentication_required", "Authentication required.")

    wrapper._tinymrp_api_auth_policy = API_AUTH_SESSION_OR_BEARER
    return wrapper


def api_token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        _, failure = authenticate_api_token()
        if failure is not None:
            return failure
        return fn(*args, **kwargs)

    wrapper._tinymrp_api_auth_policy = API_AUTH_BEARER
    return wrapper
