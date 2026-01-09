from flask import Blueprint, render_template, request, send_file, current_app, redirect, url_for, abort
import os
from io import BytesIO
from datetime import datetime

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


def _addin_root():
    return os.path.abspath(os.path.join(current_app.root_path, os.pardir, "solidworks-addin", "Windows Installer latest"))


def _addin_installers():
    root = _addin_root()
    items = []
    try:
        if os.path.isdir(root):
            for name in os.listdir(root):
                p = os.path.join(root, name)
                if os.path.isfile(p):
                    mtime = os.path.getmtime(p)
                    items.append({
                        'name': name,
                        'url': url_for('tools.addin_download', filename=name),
                        'size': os.path.getsize(p),
                        'modified': datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                        'mtime': mtime,
                    })
    except Exception:
        pass
    items.sort(key=lambda item: item.get('mtime') or 0, reverse=True)
    return items


@bp.get("/")
def tools_index():
    files = _static_tools()
    addin_files = _addin_installers()
    return render_template("tools/index.html", files=files, addin_files=addin_files)


@bp.get("/addin/latest")
def addin_latest():
    addin_files = _addin_installers()
    if not addin_files:
        return redirect(url_for('tools.tools_index'))
    target = os.path.join(_addin_root(), addin_files[0]['name'])
    if not os.path.isfile(target):
        return redirect(url_for('tools.tools_index'))
    return send_file(target, as_attachment=True, download_name=os.path.basename(target))


@bp.get("/addin/<path:filename>")
def addin_download(filename):
    root = _addin_root()
    target = os.path.abspath(os.path.join(root, filename))
    if not target.startswith(root + os.sep):
        abort(404)
    if not os.path.isfile(target):
        abort(404)
    return send_file(target, as_attachment=True, download_name=os.path.basename(target))


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
