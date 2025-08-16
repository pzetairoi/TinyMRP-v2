# app/views/ui.py
import os
from flask import Blueprint, current_app, send_from_directory, abort

bp = Blueprint("ui", __name__, url_prefix="/ui")

@bp.get("/parts")
def parts_ui():
    root = os.path.join(current_app.static_folder, "parts-ui")
    index = os.path.join(root, "index.html")
    if not os.path.exists(index):
        abort(404, description="React build not found. Run `npm run build` in /frontend.")
    return send_from_directory(root, "index.html")

@bp.get("/bom/<path:anypn>")
def bom_ui(anypn):
    # SPA route – return the same index.html and let React Router handle it
    return parts_ui()
