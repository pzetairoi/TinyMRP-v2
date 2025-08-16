# app/views/ui.py
import os
from flask import Blueprint, current_app, render_template, url_for, abort

bp = Blueprint("ui", __name__, url_prefix="/ui")

def vite_assets(entry: str = "src/main.tsx"):
    m = current_app.config.get("VITE_MANIFEST")
    if not m or entry not in m:
        return {"js": [], "css": []}
    chunk = m[entry]
    js = [url_for("static", filename=f"parts-ui/{chunk['file']}")]
    css = [url_for("static", filename=f"parts-ui/{c}") for c in chunk.get("css", [])]
    for imp in chunk.get("imports", []):
        imp_chunk = m.get(imp)
        if imp_chunk:
            js.append(url_for("static", filename=f"parts-ui/{imp_chunk['file']}"))
            css += [url_for("static", filename=f"parts-ui/{c}") for c in imp_chunk.get("css", [])]
    return {"js": js, "css": css}

@bp.get("/parts")
def parts_ui():
    assets = vite_assets()
    if not assets["js"]:
        abort(404, "React build not found. Run `npm run build` in /frontend.")
    return render_template("ui/react_shell.html", title="Parts", assets=assets, initial={})

@bp.get("/bom/<path:pn>")
def bom_ui(pn):
    assets = vite_assets()
    if not assets["js"]:
        abort(404, "React build not found. Run `npm run build` in /frontend.")
    return render_template("ui/react_shell.html", title=f"BOM · {pn}", assets=assets, initial={"pn": pn})
