from __future__ import annotations

import inspect

from flask import Blueprint

from app.extensions import csrf
from app.services.api_auth import api_auth_required
from app.views.me import get_settings
from app.views.numbering import list_schemes, preview

bp = Blueprint("legacy_addin_api", __name__, url_prefix="/api")


def _invoke_current_handler(handler):
    return inspect.unwrap(handler)()


@bp.get("/schemes")
@api_auth_required
@csrf.exempt
def legacy_schemes():
    return _invoke_current_handler(list_schemes)


@bp.get("/settings")
@api_auth_required
@csrf.exempt
def legacy_settings():
    return _invoke_current_handler(get_settings)


@bp.post("/preview")
@api_auth_required
@csrf.exempt
def legacy_preview():
    return _invoke_current_handler(preview)
