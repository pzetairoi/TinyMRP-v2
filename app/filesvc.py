# app/filesvc.py
import os, base64, mimetypes
from flask import Flask, send_file, abort
from dotenv import load_dotenv
import json as _json

def _normalize_rel(p: str) -> str:
    return p.replace("\\", "/").lstrip("/")

def _safe_join(root: str, rel: str) -> str:
    # join y normaliza evitando traversal
    abs_root = os.path.abspath(root)
    cand = os.path.abspath(os.path.join(abs_root, rel))
    if os.path.commonpath([cand, abs_root]) != abs_root:
        raise ValueError("Traversal")
    return cand

def create_files_app():
    load_dotenv()
    app = Flask("filesvc")
    try:
        app.config["FILE_ROOTS_JSON"] = _json.loads(os.getenv("FILE_ROOTS_JSON") or "[]")
    except Exception:
        app.config["FILE_ROOTS_JSON"] = []

    @app.get("/files/view/<token>")
    def view(token: str):
        try:
            path = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        except Exception:
            abort(400)
        if not os.path.isfile(path):
            abort(404)
        ct, _ = mimetypes.guess_type(path)
        resp = send_file(path, mimetype=ct or "application/octet-stream", conditional=True, max_age=3600)
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp

    @app.get("/files/static/<int:root_idx>/<path:rel_path>")
    def by_rel(root_idx: int, rel_path: str):
        roots = app.config.get("FILE_ROOTS_JSON") or []
        if root_idx < 0 or root_idx >= len(roots):
            abort(404)
        base = roots[root_idx].get("local") or ""
        if not base:
            abort(404)
        rel_path = _normalize_rel(rel_path)
        try:
            path = _safe_join(base, rel_path)
        except Exception:
            abort(400)
        if not os.path.isfile(path):
            abort(404)
        ct, _ = mimetypes.guess_type(path)
        resp = send_file(path, mimetype=ct or "application/octet-stream", conditional=True, max_age=3600)
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp

    return app

files_app = create_files_app()

if __name__ == "__main__":
    files_app.run(host="0.0.0.0", port=int(os.getenv("FILESVC_PORT") or "5055"))
