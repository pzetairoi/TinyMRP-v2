# app/views/ui.py
from flask import Blueprint, current_app, render_template, url_for, abort

bp = Blueprint("ui", __name__, url_prefix="/ui")

def vite_assets(preferred_entry: str = "src/main.tsx"):
    m = current_app.config.get("VITE_MANIFEST") or {}
    # try preferred key first, then fall back to a likely one
    key = None
    if preferred_entry in m:
        key = preferred_entry
    else:
        # pick the first sensible entry
        for k in m.keys():
            if k.endswith(("src/main.tsx","src/main.ts","src/main.jsx","src/main.js","main.tsx","main.ts","main.jsx","main.js","index.html")):
                key = k
                break
    if not key:
        return {"js": [], "css": []}

    chunk = m[key]
    js  = [url_for("static", filename=f"parts-ui/{chunk['file']}")]
    css = [url_for("static", filename=f"parts-ui/{c}") for c in chunk.get("css", [])]

    # include imported chunks (and their CSS) too
    for imp in chunk.get("imports", []):
        ic = m.get(imp)
        if ic:
            js.append(url_for("static", filename=f"parts-ui/{ic['file']}"))
            css += [url_for("static", filename=f"parts-ui/{c}") for c in ic.get("css", [])]

    return {"js": js, "css": css}

@bp.get("/parts")
def parts_ui():
    assets = vite_assets()
    if not assets["js"]:
        abort(404, f"React build missing or manifest not loaded. Looked at: {current_app.config.get('VITE_MANIFEST_PATH')}")
    return render_template("ui/react_shell.html", title="Parts", assets=assets, initial={})

@bp.get("/bom/<path:pn>")
def bom_ui(pn):
    assets = vite_assets()
    if not assets["js"]:
        abort(404, f"React build missing or manifest not loaded. Looked at: {current_app.config.get('VITE_MANIFEST_PATH')}")
    return render_template("ui/react_shell.html", title=f"BOM · {pn}", assets=assets, initial={"pn": pn})
