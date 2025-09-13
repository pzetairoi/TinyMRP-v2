import os, base64, mimetypes
from flask import Blueprint, current_app, send_file, abort
from flask_login import login_required
from app.services.audit import log_action

bp = Blueprint("fileserve", __name__, url_prefix="/files")

def _allowed_path(abs_path: str) -> bool:
    try:
        ap = os.path.abspath(abs_path)
        base = os.path.abspath((current_app.config.get("FILE_ROOT_LOCAL") or "").strip())
        if not base: return False
        # Windows-safe comparison
        ap_norm, base_norm = os.path.normcase(ap), os.path.normcase(base)
        try:
            return os.path.commonpath([ap_norm, base_norm]) == base_norm
        except Exception:
            # If drives differ, simple prefix fallback
            return ap_norm.startswith(base_norm)
    except Exception:
        return False

@bp.get("/view/<token>")
@login_required
def view(token: str):
    try:
        path = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
    except Exception:
        abort(400)
    if not os.path.isfile(path) or not _allowed_path(path):
        abort(404)
    ct, _ = mimetypes.guess_type(path)
    # Compute relative path for logging (avoid absolute disks)
    rel = path
    try:
        base = (current_app.config.get("FILE_ROOT_LOCAL") or "").strip()
        if base and rel.lower().startswith(base.strip().lower()):
            rel = rel[len(base):].lstrip("/\\")
    except Exception:
        pass
    try:
        log_action("file.view", resource_type="file", resource=rel)
    except Exception:
        pass
    resp = send_file(path, mimetype=ct or "application/octet-stream",
                     conditional=True, max_age=3600)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp
