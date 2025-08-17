from flask import Blueprint, request, jsonify, current_app
from app.extensions import csrf
from app.models.artifact import PartFile
import base64

bp = Blueprint("files_api", __name__, url_prefix="/api")

def _token_url(path: str) -> str:
    tok = base64.urlsafe_b64encode((path or "").encode("utf-8")).decode("ascii")
    return f"/files/view/{tok}"

@bp.get("/part_images")
@csrf.exempt
def part_images():
    pn  = (request.args.get("pn") or "").strip()
    rev = (request.args.get("rev") or "").strip()
    if not pn: return jsonify([])

    q = {"part_number": pn, "ext_group__in": ["png"]}
    if rev: q["revision"] = rev
    docs = list(PartFile.objects(**q).order_by("-mtime", "path"))
    if not rev and docs:
        latest_rev = docs[0].revision
        docs = [d for d in docs if d.revision == latest_rev]

    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")
    out = []
    for d in docs:
        urls = []
        rel = getattr(d, "rel_path", "") or ""
        if http_base and rel:
            urls.append(f"{http_base}/{rel}")   # preferred
        urls.append(_token_url(getattr(d, "path", "")))  # fallback
        out.append({
            "urls": urls,
            "best": urls[0] if urls else "",
            "revision": d.revision,
            "ext": d.ext,
            "group": d.ext_group,
            "mtime": d.mtime.isoformat() if d.mtime else None,
        })
    return jsonify(out)
