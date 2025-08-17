# app/views/fileserve.py
import os, base64, mimetypes
from flask import Blueprint, current_app, send_file, abort

bp = Blueprint("fileserve", __name__, url_prefix="/files")

def _allowed_path(abs_path: str) -> bool:
    """
    Returns True if abs_path is inside ANY configured FILE_ROOTS_JSON[i].local.
    Robust on Windows: tolerates different drives by skipping those comparisons.
    """
    try:
        ap = os.path.abspath(abs_path)
    except Exception:
        return False

    roots = current_app.config.get("FILE_ROOTS_JSON") or []
    for r in roots:
        local = (r.get("local") or "").strip()
        if not local:
            continue
        try:
            base = os.path.abspath(local)
            # Normalize case for Windows comparisons
            ap_norm   = os.path.normcase(ap)
            base_norm = os.path.normcase(base)
            try:
                common = os.path.commonpath([ap_norm, base_norm])
            except ValueError:
                # Different drives (e.g., Z:\ vs \\server\), just skip this root
                continue
            if common == base_norm:
                return True
        except Exception:
            continue
    return False

@bp.get("/view/<token>")
def view(token: str):
    try:
        path = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
    except Exception:
        abort(400)
    if not os.path.isfile(path) or not _allowed_path(path):
        abort(404)
    ct, _ = mimetypes.guess_type(path)
    resp = send_file(path, mimetype=ct or "application/octet-stream",
                     conditional=True, max_age=3600)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp
