from __future__ import annotations

import json
import os
from typing import Any

from flask import Blueprint, current_app, render_template
from flask_login import login_required

bp = Blueprint("help", __name__)


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
