import os, requests, ipaddress
from urllib.parse import urlparse
from flask import Blueprint, request, Response, stream_with_context, current_app, abort
from flask_login import login_required, current_user
from app.services.authorization import require_permission
from app.services.file_security import readable_managed_file_for_rel_path
from app.models.artifact import PartFile

files_proxy = Blueprint("files_proxy", __name__)

def _normalize_rel(rel: str) -> str:
    rel_norm = (rel or "").replace("\\", "/").lstrip("/")
    return os.path.normpath(rel_norm).replace("\\", "/")


def _authorize_rel_path(rel_path: str) -> PartFile:
    rel_norm = _normalize_rel(rel_path)
    if not rel_norm or rel_norm.startswith(".."):
        abort(404)
    record = readable_managed_file_for_rel_path(current_user, rel_norm)
    if record is None:
        abort(404)
    return record


def _proxy(up_path: str, *, rel_path: str | None = None):
    upstream = (current_app.config.get("FILES_UPSTREAM_BASE") or "").strip().rstrip("/")
    if not upstream:
        # Upstream not configured -> disable proxy endpoints
        abort(404)
    try:
        parsed = urlparse(upstream)
    except Exception:
        abort(404)
    if parsed.scheme not in ("http", "https"):
        abort(404)
    if parsed.username or parsed.password:
        abort(404)
    if not parsed.hostname:
        abort(404)
    # Optional upstream allowlist
    allowed_raw = (
        current_app.config.get("FILES_UPSTREAM_ALLOWED_HOSTS")
        or os.getenv("FILES_UPSTREAM_ALLOWED_HOSTS")
        or ""
    )
    allowed_hosts = [h.strip().lower() for h in str(allowed_raw).split(",") if h.strip()]
    if allowed_hosts and parsed.hostname.lower() not in allowed_hosts:
        abort(403)
    # Block direct IP literals unless explicitly allowlisted.
    try:
        ipaddress.ip_address(parsed.hostname)
        if not allowed_hosts:
            abort(403)
    except ValueError:
        pass
    if rel_path:
        file_record = _authorize_rel_path(rel_path)
        canonical_rel = str(file_record.rel_path or "").replace("\\", "/").lstrip("/")
        up_path = (
            f"deliverables/{canonical_rel}"
            if up_path.lower().startswith("deliverables/")
            else canonical_rel
        )
    url = f"{upstream}/{up_path.lstrip('/')}"
    headers = {}
    if "Range" in request.headers:
        headers["Range"] = request.headers["Range"]
    upstream_resp = requests.get(url, headers=headers, stream=True, timeout=30, allow_redirects=False)

    max_bytes = int(current_app.config.get("FILES_PROXY_MAX_BYTES") or 0)
    try:
        if max_bytes and upstream_resp.headers.get("Content-Length"):
            if int(upstream_resp.headers.get("Content-Length") or 0) > max_bytes:
                abort(413)
        elif max_bytes:
            abort(413)
    except Exception:
        if max_bytes:
            abort(413)

    def gen():
        total = 0
        for chunk in upstream_resp.iter_content(chunk_size=64*1024):
            if chunk:
                total += len(chunk)
                if max_bytes and total > max_bytes:
                    try:
                        upstream_resp.close()
                    except Exception:
                        pass
                    break
                yield chunk

    resp = Response(stream_with_context(gen()), status=upstream_resp.status_code)
    if max_bytes:
        resp.headers.setdefault("X-Content-Limit", str(max_bytes))
    for h in [
        "Content-Type","Content-Length","Content-Range","Accept-Ranges",
        "ETag","Last-Modified","Cache-Control","Expires"
    ]:
        if h in upstream_resp.headers:
            resp.headers[h] = upstream_resp.headers[h]
    return resp

@files_proxy.route("/extfiles/<path:rest>")          # e.g. /extfiles/deliverables/3mf/file.3mf
@login_required
@require_permission("files.read")
def extfiles(rest: str):
    rel = rest
    if rel.lower().startswith("deliverables/"):
        rel = rel.split("/", 1)[1]
    return _proxy(rest, rel_path=rel)

@files_proxy.route("/deliverables/<path:rest>")      # also allow direct /deliverables/*
@login_required
@require_permission("files.read")
def deliverables(rest: str):
    return _proxy(f"deliverables/{rest}", rel_path=rest)
