import os
import mimetypes
from flask import Blueprint, abort, send_file
from flask_login import current_user, login_required

from app.services.acl import allowed_parts_for, part_is_allowed
from app.services.extra_files import resolve_extra_file_token, extra_abs_path, extra_root


bp = Blueprint("extra_fileserve", __name__, url_prefix="/extra")


def _allowed_path(abs_path: str, base_root: str) -> bool:
    try:
        ap = os.path.abspath(abs_path)
        base = os.path.abspath(base_root)
        ap_norm, base_norm = os.path.normcase(ap), os.path.normcase(base)
        try:
            return os.path.commonpath([ap_norm, base_norm]) == base_norm
        except Exception:
            return ap_norm.startswith(base_norm)
    except Exception:
        return False


@bp.get("/view/<token>")
@login_required
def view(token: str):
    resolved = resolve_extra_file_token(token)
    if not resolved:
        abort(404)
    ef, _kind = resolved

    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, ef.part_number, ef.revision or ""):
            return abort(403)
    except Exception:
        pass

    base_root = extra_root()
    if not base_root:
        abort(404)
    abs_path = extra_abs_path(ef.rel_path or "")
    if not abs_path or not _allowed_path(abs_path, base_root) or not os.path.isfile(abs_path):
        abort(404)

    ct = ef.mime or mimetypes.guess_type(abs_path)[0] or "application/octet-stream"
    resp = send_file(abs_path, mimetype=ct, conditional=True, max_age=3600)
    resp.headers["Cache-Control"] = "private, max-age=3600"
    return resp
