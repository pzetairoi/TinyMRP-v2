# app/files_proxy.py
import os, requests
from flask import Blueprint, request, Response, stream_with_context

files_proxy = Blueprint("files_proxy", __name__)
UPSTREAM = os.getenv("FILES_UPSTREAM_BASE", "http://192.168.0.198").rstrip("/")

def _proxy(up_path: str):
    url = f"{UPSTREAM}/{up_path.lstrip('/')}"
    headers = {}
    if "Range" in request.headers:
        headers["Range"] = request.headers["Range"]
    upstream = requests.get(url, headers=headers, stream=True, timeout=30)

    def gen():
        for chunk in upstream.iter_content(chunk_size=64*1024):
            if chunk:
                yield chunk

    resp = Response(stream_with_context(gen()), status=upstream.status_code)
    for h in [
        "Content-Type","Content-Length","Content-Range","Accept-Ranges",
        "ETag","Last-Modified","Cache-Control","Expires"
    ]:
        if h in upstream.headers:
            resp.headers[h] = upstream.headers[h]
    return resp

@files_proxy.route("/extfiles/<path:rest>")          # e.g. /extfiles/Deliverables/3mf/file.3mf
def extfiles(rest: str):
    return _proxy(rest)

@files_proxy.route("/Deliverables/<path:rest>")      # also allow direct /Deliverables/*
def deliverables(rest: str):
    return _proxy(f"Deliverables/{rest}")
