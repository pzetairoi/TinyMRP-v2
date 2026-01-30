import mimetypes
import os

from flask import Blueprint, current_app, redirect, send_file, url_for

from app.services.app_settings import resolve_brand_logo_path

bp = Blueprint("branding", __name__, url_prefix="/branding")


@bp.get("/logo")
def logo():
    path = resolve_brand_logo_path()
    if path and os.path.isfile(path):
        mime, _ = mimetypes.guess_type(path)
        return send_file(
            path,
            mimetype=mime or "application/octet-stream",
            conditional=True,
            max_age=current_app.config.get("BRANDING_LOGO_CACHE_SECONDS", 300),
        )
    return redirect(url_for("static", filename="images/logo.png"))
