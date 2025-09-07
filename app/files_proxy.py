import os, requests
from flask import Blueprint, request, Response, stream_with_context, current_app, abort

files_proxy = Blueprint("files_proxy", __name__)

def _proxy(up_path: str):
    upstream = (current_app.config.get("FILES_UPSTREAM_BASE") or "").strip().rstrip("/")
    if not upstream:
        # Upstream not configured -> disable proxy endpoints
        abort(404)
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
def extfiles(rest: str):
    return _proxy(rest)

@files_proxy.route("/deliverables/<path:rest>")      # also allow direct /deliverables/*
def deliverables(rest: str):
    return _proxy(f"deliverables/{rest}")
