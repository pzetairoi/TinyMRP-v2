# app/views/files.py
from flask import Blueprint, request, jsonify, current_app
from app.extensions import csrf
from app.models.artifact import PartFile
import base64

bp = Blueprint("files_api", __name__, url_prefix="/api")

def _roots():
    return current_app.config.get("FILE_ROOTS_JSON") or []

def _token_url(path: str) -> str:
    tok = base64.urlsafe_b64encode((path or "").encode("utf-8")).decode("ascii")
    return f"/files/view/{tok}"

def _http_bases_for(doc: PartFile) -> list[str]:
    roots = _roots()
    idx = getattr(doc, "root_idx", None)
    if idx is None or not isinstance(idx, int) or idx < 0 or idx >= len(roots):
        return []
    http = roots[idx].get("http")
    if not http:
        return []
    if isinstance(http, str):
        return [http]
    if isinstance(http, list):
        return [h for h in http if isinstance(h, str) and h.strip()]
    return []

@bp.get("/part_images")
@csrf.exempt
def part_images():
    pn  = (request.args.get("pn") or "").strip()
    rev = (request.args.get("rev") or "").strip()
    if not pn:
        return jsonify([])

    q = {"part_number": pn, "ext_group__in": ["png"]}
    if rev:
        q["revision"] = rev
    docs = list(PartFile.objects(**q).order_by("-mtime", "path"))

    if not rev and docs:
        latest_rev = docs[0].revision
        docs = [d for d in docs if d.revision == latest_rev]

    out = []
    for d in docs:
        urls: list[str] = []
        for base in _http_bases_for(d):
            rel = getattr(d, "rel_path", "")
            if rel:
                urls.append(f"{base.rstrip('/')}/{rel}")
        urls.append(_token_url(getattr(d, "path", "")))
        for extra in (getattr(d, "meta_info", {}) or {}).get("external_urls", []):
            if isinstance(extra, str) and extra and extra not in urls:
                urls.append(extra)
        out.append({
            "urls": urls,
            "best": urls[0] if urls else "",
            "revision": d.revision,
            "ext": d.ext,
            "group": d.ext_group,
            "mtime": d.mtime.isoformat() if d.mtime else None,
        })
    return jsonify(out)
