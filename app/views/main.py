import os
from flask import Blueprint, render_template, send_file, abort
from flask_security import auth_required, current_user

bp = Blueprint("main", __name__)

def _latest_file(root: str, patterns: list[str]) -> str | None:
    latest = None
    latest_mtime = -1.0
    if not root or not os.path.isdir(root):
        return None
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if not any(name.lower().endswith(pat) for pat in patterns):
                continue
            path = os.path.join(dirpath, name)
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                continue
            if mtime > latest_mtime:
                latest = path
                latest_mtime = mtime
    return latest

@bp.route("/")
def index():
    return render_template("index.html")

@bp.route("/app")
@auth_required()
def app_home():
    return render_template("home.html", user=current_user)


@bp.get("/downloads/macro")
def download_macro():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "OLD", "SourceCode", "app", "static", "misc"))
    path = _latest_file(root, [".swp"])
    if not path or not os.path.isfile(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@bp.get("/downloads/addin")
def download_addin():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "solidworks-addin", "Windows Installer latest"))
    path = _latest_file(root, [".exe", ".msi"])
    if not path or not os.path.isfile(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))
