from __future__ import annotations

import os

from flask import Blueprint, current_app, jsonify

from app.services.security_mode import security_mode

bp = Blueprint("api_health", __name__, url_prefix="/api")


def _server_version() -> str:
    value = current_app.config.get("APP_VERSION") or os.getenv("APP_VERSION") or os.getenv("GIT_COMMIT")
    return str(value or "dev")


@bp.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "tinymrp",
        "server_version": _server_version(),
        "security_mode": security_mode(),
    })
