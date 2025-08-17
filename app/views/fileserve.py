# app/views/fileserve.py
import os, base64, mimetypes
from flask import Blueprint, current_app, send_file, abort

bp = Blueprint("fileserve", __name__, url_prefix="/files")

def _allowed_path(abs_path: str) -> bool:
    roots = current_app.config.get("FILE_ROOTS_JSON") or []
    abs_path = os.path.abspath(abs_path)
    for r in roots:
        root = os.path.abspath(r.get("local") or "")
        if root and os.path.commonpath([abs_path, root]) == root:
            return True
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
    resp = send_file(path, mimetype=ct or "application/octet-stream", conditional=True, max_age=3600)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp
