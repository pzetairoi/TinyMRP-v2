import mimetypes
from flask import Blueprint, abort, send_file
from flask_login import current_user, login_required

from app.services.extra_files import resolve_extra_file_token
from app.services.file_security import (
    FileSecurityError,
    associated_file_read_allowed,
    resolve_associated_path,
)


bp = Blueprint("extra_fileserve", __name__, url_prefix="/extra")


@bp.get("/view/<token>")
@login_required
def view(token: str):
    resolved = resolve_extra_file_token(token)
    if not resolved:
        abort(404)
    ef, _kind = resolved

    if not associated_file_read_allowed(current_user, ef):
        abort(404)
    try:
        abs_path = resolve_associated_path(ef)
    except FileSecurityError:
        abort(404)

    ct = ef.mime or mimetypes.guess_type(str(abs_path))[0] or "application/octet-stream"
    resp = send_file(abs_path, mimetype=ct, conditional=True, max_age=3600)
    resp.headers["Cache-Control"] = "private, max-age=3600"
    return resp
