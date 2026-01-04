from __future__ import annotations

from datetime import datetime
from functools import wraps
from typing import Optional, Tuple

from flask import request, jsonify, g
from flask_security import current_user

from app.models.auth import User
from app.services.api_tokens import verify_token, touch_last_used


def _extract_token() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    token = request.headers.get("Authentication-Token", "").strip()
    if token:
        return token
    return request.headers.get("X-Auth-Token", "").strip()


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


def api_auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token_value = _extract_token()
        if token_value:
            user, token_id = _user_from_token(token_value)
            if user:
                g.api_user = user
                g.api_token_id = token_id
                return fn(*args, **kwargs)

        if getattr(current_user, "is_authenticated", False):
            return fn(*args, **kwargs)

        return jsonify({
            "ok": False,
            "error": {"code": "unauthorized", "message": "Authentication required.", "details": []},
        }), 401

    return wrapper
