from flask import Blueprint, request, jsonify
from app.services.api_auth import api_auth_required

legacy = Blueprint("legacy_addin", __name__)

@legacy.get("/api/health")
def health():
    return jsonify(ok=True), 200

@legacy.get("/api/schemes")
@api_auth_required
def schemes_alias():
    # call the real endpoint internally by redirecting logic
    # simplest: return same as /api/numbering/schemes by importing its view
    from app.views.numbering_api import numbering_schemes_list  # adjust import to your file name
    return numbering_schemes_list()

@legacy.get("/api/settings")
@api_auth_required
def settings_alias():
    from app.views.me_api import me_settings_get  # adjust import to your file name
    return me_settings_get()

@legacy.post("/api/preview")
@api_auth_required
def preview_alias():
    from app.views.numbering_api import numbering_preview  # adjust import to your file name
    return numbering_preview()
