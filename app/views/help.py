from __future__ import annotations

import io
import json
import os
import threading
from typing import Any

from flask import Blueprint, current_app, render_template, send_file
from flask_login import login_required

bp = Blueprint("help", __name__)

# The eleven-step import exercise is built from the checked-in CV03 sample
# fixture (see app/services/import_practice_packs.py), which never changes
# while a process is running, so the ZIP is built once per worker and reused
# rather than re-zipped on every click.
_PRACTICE_PACK_PREFIX = "IMPTEST-"
_practice_pack_cache: dict[str, bytes] = {}
_practice_pack_lock = threading.Lock()


def _practice_pack_bundle() -> bytes:
    cached = _practice_pack_cache.get(_PRACTICE_PACK_PREFIX)
    if cached is not None:
        return cached
    with _practice_pack_lock:
        cached = _practice_pack_cache.get(_PRACTICE_PACK_PREFIX)
        if cached is not None:
            return cached
        from app.services.import_practice_packs import build_bundle_bytes

        data = build_bundle_bytes(_PRACTICE_PACK_PREFIX)
        _practice_pack_cache[_PRACTICE_PACK_PREFIX] = data
        return data


def _help_static_dir() -> str:
    return current_app.config.get("HELP_STATIC_DIR") or current_app.static_folder


def _help_html_path() -> str:
    return os.path.join(_help_static_dir(), "help", "help.html")


def _help_toc_path() -> str:
    return os.path.join(_help_static_dir(), "help", "help_toc.json")


def _load_json(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


@bp.get("/help")
@login_required
def help_index():
    help_html = ""
    help_missing = False
    html_path = _help_html_path()
    if os.path.isfile(html_path):
        with open(html_path, encoding="utf-8") as f:
            help_html = f.read()
    else:
        help_missing = True

    toc = _load_json(_help_toc_path())
    toc_items = toc.get("items") if isinstance(toc.get("items"), list) else []
    return render_template(
        "help/index.html",
        help_html=help_html,
        help_missing=help_missing,
        toc_items=toc_items,
        toc_meta={
            "generated_at": toc.get("generated_at") or "",
            "commit": toc.get("commit") or "",
        },
    )


@bp.get("/help/practice-packs.zip")
@login_required
def practice_packs():
    """The eleven-step import exercise, ready to unzip and upload.

    Generated on demand from the checked-in CV03 sample rather than shipped as
    a static file, so it can never drift from the generator that documents it
    in the help text.
    """
    try:
        data = _practice_pack_bundle()
    except Exception:
        current_app.logger.exception("could not build the import practice-pack bundle")
        return "Could not build the practice-pack bundle.", 500
    return send_file(
        io.BytesIO(data),
        mimetype="application/zip",
        as_attachment=True,
        download_name="tinymrp-import-practice-packs.zip",
        max_age=0,
    )
