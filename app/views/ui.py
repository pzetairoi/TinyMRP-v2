# app/views/ui.py
import os
from flask import Blueprint, current_app, render_template, url_for, abort

bp = Blueprint("ui", __name__, url_prefix="/ui")

def _file_exists(rel_from_static: str) -> bool:
    abs_path = os.path.join(current_app.static_folder, rel_from_static.replace("/", os.sep))
    return os.path.exists(abs_path)

def vite_assets():
    m = current_app.config.get("VITE_MANIFEST") or {}
    # Find a plausible entry key
    candidates = ["src/main.tsx", "src/main.ts", "src/main.jsx", "src/main.js", "index.html"]
    key = next((k for k in candidates if k in m), None)
    if not key:
        # pick first .js entry in manifest
        for k, v in m.items():
            if isinstance(v, dict) and str(v.get("file","")).endswith(".js"):
                key = k
                break
    js, css = [], []
    if key:
        chunk = m.get(key, {})
        js_file = chunk.get("file")
        css_files = chunk.get("css", [])
        if js_file:
            rel = f"parts-ui/{js_file}"
            # FALLBACK: if manifest points to stale file, scan the dir for index-*.js
            if not _file_exists(rel):
                assets_dir = os.path.join(current_app.static_folder, "parts-ui", "assets")
                try:
                    from glob import glob
                    picks = sorted(glob(os.path.join(assets_dir, "index-*.js")), key=os.path.getmtime, reverse=True)
                    if picks:
                        # convert to rel path from static
                        rel = "parts-ui/assets/" + os.path.basename(picks[0])
                except Exception:
                    pass
            js.append(url_for("static", filename=rel))
        for c in css_files:
            css.append(url_for("static", filename=f"parts-ui/{c}"))
        # include imports
        for imp in chunk.get("imports", []):
            imp_chunk = m.get(imp) or {}
            imp_file = imp_chunk.get("file")
            if imp_file:
                js.append(url_for("static", filename=f"parts-ui/{imp_file}"))
            for c in imp_chunk.get("css", []):
                css.append(url_for("static", filename=f"parts-ui/{c}"))
    return {"js": js, "css": css}

@bp.get("/parts")
def parts_ui():
    assets = vite_assets()
    if not assets["js"]:
        abort(404, "React build missing. Run `npm run build` in /frontend.")
    return render_template("ui/react_shell.html", title="Parts", assets=assets, initial={})

@bp.get("/bom/<path:pn>")
def bom_ui(pn):
    assets = vite_assets()
    if not assets["js"]:
        abort(404, "React build missing. Run `npm run build` in /frontend.")
    return render_template("ui/react_shell.html", title=f"BOM · {pn}", assets=assets, initial={"pn": pn})
