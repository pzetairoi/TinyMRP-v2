from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Tuple

from flask import jsonify, request

from app.services.api_auth import get_request_user
from app.services.acl import user_has_permission


def json_error(code: str, message: str, status: int = 400, details: list | None = None):
    return jsonify({
        "ok": False,
        "error": {"code": code, "message": message, "details": details or []},
    }), status


def ensure_permissions(*perms: str):
    user = get_request_user()
    if not user:
        return None, json_error("unauthorized", "Authentication required.", 401)
    try:
        for r in (user.roles or []):
            if getattr(r, "name", "") == "admin":
                return user, None
    except Exception:
        pass
    for p in perms:
        if not user_has_permission(user, p):
            return user, json_error("forbidden", "Permission denied.", 403)
    return user, None


def parse_pagination(default_size: int = 20, max_size: int = 100) -> Tuple[int, int]:
    try:
        page = int(request.args.get("page", 1))
    except Exception:
        page = 1
    try:
        size = int(request.args.get("page_size", default_size))
    except Exception:
        size = default_size
    page = max(page, 1)
    size = max(1, min(size, max_size))
    return page, size


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def get_json() -> Dict[str, Any]:
    return request.get_json(silent=True) or {}
