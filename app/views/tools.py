from flask import Blueprint, render_template, request, send_file, current_app, redirect, url_for
import os
from io import BytesIO

bp = Blueprint("tools", __name__, url_prefix="/tools")


def _static_tools():
    root = os.path.join(current_app.root_path, 'static', 'tools')
    items = []
    try:
        if os.path.isdir(root):
            for name in sorted(os.listdir(root)):
                p = os.path.join(root, name)
                if os.path.isfile(p):
                    items.append({
                        'name': name,
                        'url': f"/static/tools/{name}",
                        'size': os.path.getsize(p)
                    })
    except Exception:
        pass
    return items


@bp.get("/")
def tools_index():
    files = _static_tools()
    return render_template("tools/index.html", files=files)


@bp.route("/excel_bom", methods=["GET", "POST"])
def excel_bom():
    if request.method == 'POST':
        pn = (request.form.get('pn') or '').strip()
        rev = (request.form.get('rev') or '').strip()
        depth = (request.form.get('depth') or 'full').strip().lower()
        if not pn:
            return redirect(url_for('tools.excel_bom'))
        # Proxy to the docpacks builder to create an Excel BOM only
        from app.services.docpacks import DocPackOptions, build_docpack
        opts = DocPackOptions(root_pn=pn, root_rev=rev or None, depth=depth,
                              want_excel_bom=True, want_selected_files=False,
                              want_pdf_binder=False, want_visual_list=False)
        name, data, mime = build_docpack(opts)
        bio = BytesIO(data)
        return send_file(bio, mimetype=mime, as_attachment=True, download_name=name)
    return render_template("tools/excel_bom.html")

