# app/views/files.py
from flask import Blueprint, request, jsonify, current_app
from app.extensions import csrf
from app.models.artifact import PartFile
import base64

bp = Blueprint("files_api", __name__, url_prefix="/api")

def _roots():
    return current_app.config.get("FILE_ROOTS_JSON") or []

def _token_url(path: str) -> str:
    tok = base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii")
    return f"/files/view/{tok}"

def _http_bases_for(doc: PartFile) -> list[str]:
    roots = _roots()
    if doc.root_idx is None or doc.root_idx >= len(roots):
        return []
    http = roots[doc.root_idx].get("http")
    if not http:
        return []
    if isinstance(http, str):
        return [http]
    if isinstance(http, list):
        return [h for h in http if isinstance(h, str) and h.strip()]
    return []

def _filesvc_url(doc: PartFile) -> str | None:
    base = (current_app.config.get("FILESVC_PUBLIC_BASE") or "").strip()
    if not base or not doc.rel_path:
        return None
    return f"{base.rstrip('/')}/{doc.root_idx}/{doc.rel_path}"

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
        # 1) external HTTP bases (can be several, priority order)
        for base in _http_bases_for(d):
            if d.rel_path:
                urls.append(f"{base.rstrip('/')}/{d.rel_path}")
        # 2) micro-service (if configured)
        fs = _filesvc_url(d)
        if fs:
            urls.append(fs)
        # 3) app-served token fallback
        urls.append(_token_url(d.path))
        # 4) any extras you stored
        for extra in (d.meta_info or {}).get("external_urls", []):
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
