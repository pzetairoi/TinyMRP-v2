# app/views/files.py
from flask import Blueprint, request, jsonify, current_app
from app.models.artifact import PartFile
from app.extensions import csrf
import os, base64

bp = Blueprint("files_api", __name__, url_prefix="/api")

def _roots():
    return current_app.config.get("FILE_ROOTS_JSON") or []

def _app_token_url(path: str) -> str:
    tok = base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii")
    return f"/files/view/{tok}"

def _http_bases_for(doc: PartFile) -> list[str]:
    """Devuelve lista de bases HTTP (ordenadas) configuradas para ese root."""
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
    # /files/static/<root_idx>/<rel_path>
    return f"{base.rstrip('/')}/{doc.root_idx}/{doc.rel_path}"

@bp.get("/part_images")
@csrf.exempt
def part_images():
    pn  = (request.args.get("pn") or "").strip()
    rev = (request.args.get("rev") or "").strip()
    if not pn:
        return jsonify([])

    # Solo imágenes de carpeta 'png' (según tu estructura). Añadir más grupos si procede.
    q = {"part_number": pn, "ext_group__in": ["png"]}
    if rev: q["revision"] = rev
    docs = list(PartFile.objects(**q).order_by("-mtime", "path"))
    print("DOCS",docs)

    if not rev and docs:
        latest_rev = docs[0].revision
        docs = [d for d in docs if d.revision == latest_rev]

    out = []
    for d in docs:
        urls: list[str] = []

        # 1) HTTP externos del root (pueden ser varios)
        for base in _http_bases_for(d):
            if d.rel_path:
                urls.append(f"{base.rstrip('/')}/{d.rel_path}")

        # 2) Micro-servicio (si está configurado)
        fs = _filesvc_url(d)
        if fs:
            urls.append(fs)

        # 3) Fallback token servido por la app principal
        urls.append(_app_token_url(d.path))

        # 4) Extras registrados en meta_info.external_urls
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
        print(out)
    return jsonify(out)
