# app/views/ui.py
import json, os
from flask import Blueprint, render_template, abort, current_app, request
from flask_login import login_required
from flask_security import current_user

bp = Blueprint("ui", __name__, url_prefix="/ui")

def vite_assets():
    """
    Reads app/static/parts-ui/.vite/manifest.json and returns absolute URLs
    for the main JS and CSS entry. Returns strings, not lists.
    """
    static_root = os.path.join(current_app.root_path, "static", "parts-ui")
    manifest_path = os.path.join(static_root, ".vite", "manifest.json")
    if not os.path.isfile(manifest_path):
        return {"js": None, "css": None}

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Find the entry marked isEntry (Vite)
    entry = None
    for _, v in manifest.items():
        if v.get("isEntry"):
            entry = v
            break

    if not entry:
        return {"js": None, "css": None}

    js_file = entry.get("file")                  # e.g. assets/index-XXXX.js
    css_files = entry.get("css") or []           # e.g. ["assets/index-XXXX.css"]

    js_url = f"/static/parts-ui/{js_file}" if js_file else None
    css_url = f"/static/parts-ui/{css_files[0]}" if css_files else None

    return {"js": js_url, "css": css_url}

@bp.get("/parts")
@login_required
def parts_ui():
    assets = vite_assets()
    if not assets["js"]:
        abort(404, "React build missing. Run `npm run build` in /frontend.")
    files_base = (current_app.config.get("FILE_ROOT_HTTP") or current_app.config.get("FILES_URL_PREFIX") or "").rstrip("/")
    return render_template("ui/react_shell.html", title="Parts", assets=assets, initial={}, files_base=files_base)

@bp.get("/bom/<path:pn>")
@login_required
def bom_ui(pn):
    assets = vite_assets()
    if not assets["js"]:
        abort(404, "React build missing. Run `npm run build` in /frontend.")
    # revision-aware initial state for React app
    rev = (request.args.get("rev") or "").strip()
    return render_template(
        "ui/react_shell.html",
        title=f"BOM · {pn}{(' · REV ' + rev) if rev else ''}",
        assets=assets,
        initial={"pn": pn, "rev": rev},
    )


@bp.get("/addin/tokens")
@login_required
def addin_tokens_ui():
    assets = vite_assets()
    if not assets["js"]:
        abort(404, "React build missing. Run `npm run build` in /frontend.")
    return render_template("ui/react_shell.html", title="API Tokens", assets=assets, initial={})


@bp.get("/admin/addin")
@login_required
def admin_addin_ui():
    if not getattr(current_user, "has_role", None) or not current_user.has_role("admin"):
        abort(403)
    assets = vite_assets()
    if not assets["js"]:
        abort(404, "React build missing. Run `npm run build` in /frontend.")
    return render_template("ui/react_shell.html", title="Add-in Admin", assets=assets, initial={})

@bp.get("/part/<path:pn>")
@login_required
def part_ui(pn):
    assets = vite_assets()
    if not assets["js"]:
        abort(404, "React build missing. Run `npm run build` in /frontend.")
    # revision-aware initial state for React app
    rev = (request.args.get("rev") or "").strip()
    return render_template(
        "ui/react_shell.html",
        title=f"Part · {pn}{(' · REV ' + rev) if rev else ''}",
        assets=assets,
        initial={"pn": pn, "rev": rev},
    )
