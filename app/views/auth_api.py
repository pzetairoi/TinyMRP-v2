from __future__ import annotations

from flask import Blueprint, jsonify, current_app

from app.services.api_auth import api_token_required, get_request_user

bp = Blueprint("auth_api", __name__, url_prefix="/api/auth")


@bp.get("/check")
@api_token_required
def auth_check():
    user = get_request_user()
    return jsonify({
        "ok": True,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "roles": [r.name for r in (user.roles or [])],
        },
        "server_version": current_app.config.get("APP_VERSION", "dev"),
    })
