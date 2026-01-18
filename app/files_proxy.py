import os, requests
from flask import Blueprint, request, Response, stream_with_context, current_app, abort
from flask_login import login_required, current_user
from mongoengine.queryset.visitor import Q
from app.services.acl import require_items_view, allowed_parts_for, part_is_allowed
from app.models.artifact import PartFile

files_proxy = Blueprint("files_proxy", __name__)

def _normalize_rel(rel: str) -> str:
    rel_norm = (rel or "").replace("\\", "/").lstrip("/")
    return os.path.normpath(rel_norm).replace("\\", "/")


def _authorize_rel_path(rel_path: str) -> None:
    rel_norm = _normalize_rel(rel_path)
    if not rel_norm or rel_norm.startswith(".."):
        abort(404)
    pf = PartFile.objects(Q(rel_path=rel_norm) | Q(rel_path__iexact=rel_norm)).first()
    if not pf:
        abort(404)
    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, pf.part_number, pf.revision or ""):
            abort(403)
    except Exception:
        abort(403)


def _proxy(up_path: str, *, rel_path: str | None = None):
    upstream = (current_app.config.get("FILES_UPSTREAM_BASE") or "").strip().rstrip("/")
    if not upstream:
        # Upstream not configured -> disable proxy endpoints
        abort(404)
    if rel_path:
        _authorize_rel_path(rel_path)
    url = f"{upstream}/{up_path.lstrip('/')}"
    headers = {}
    if "Range" in request.headers:
        headers["Range"] = request.headers["Range"]
    upstream_resp = requests.get(url, headers=headers, stream=True, timeout=30)

    def gen():
        for chunk in upstream_resp.iter_content(chunk_size=64*1024):
            if chunk:
                yield chunk

    resp = Response(stream_with_context(gen()), status=upstream_resp.status_code)
    for h in [
        "Content-Type","Content-Length","Content-Range","Accept-Ranges",
        "ETag","Last-Modified","Cache-Control","Expires"
    ]:
        if h in upstream_resp.headers:
            resp.headers[h] = upstream_resp.headers[h]
    return resp

@files_proxy.route("/extfiles/<path:rest>")          # e.g. /extfiles/deliverables/3mf/file.3mf
@login_required
@require_items_view
def extfiles(rest: str):
    rel = rest
    if rel.lower().startswith("deliverables/"):
        rel = rel.split("/", 1)[1]
    return _proxy(rest, rel_path=rel)

@files_proxy.route("/deliverables/<path:rest>")      # also allow direct /deliverables/*
@login_required
@require_items_view
def deliverables(rest: str):
    return _proxy(f"deliverables/{rest}", rel_path=rest)
