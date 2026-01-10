from flask import Blueprint, render_template, request, send_file, current_app, redirect, url_for, abort, flash
import os
from io import BytesIO
from datetime import datetime
from flask_login import login_required

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


@bp.route("/excelcompile", methods=["GET", "POST"])
@login_required
def excel_compile():
    if request.method == "POST":
        up = request.files.get("file")
        if not up or not up.filename:
            flash("Select an Excel file to upload.")
            return render_template("tools/excel_compile.html", upload=False, filepath=None, missing=[])

        ext = os.path.splitext(up.filename)[1].lower()
        if ext != ".xlsx":
            flash("Only .xlsx files are supported.")
            return render_template("tools/excel_compile.html", upload=False, filepath=None, missing=[])

        raw = up.read()
        if not raw:
            flash("Uploaded file was empty.")
            return render_template("tools/excel_compile.html", upload=False, filepath=None, missing=[])

        # Save a temporary copy for parsing
        temp_root = os.path.join(current_app.instance_path, "excelcompile")
        os.makedirs(temp_root, exist_ok=True)
        temp_input = os.path.join(temp_root, "upload_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f") + ".xlsx")
        with open(temp_input, "wb") as f:
            f.write(raw)

        from app.services.excel_compile import parse_compile_excel, build_excel_compile_zip
        try:
            rows = parse_compile_excel(temp_input)
            if not rows:
                flash("No valid rows found. Ensure the sheet is named COMPILE and has a PartNumber column.")
                return render_template("tools/excel_compile.html", upload=False, filepath=None, missing=[])

            file_root = (current_app.config.get("FILE_ROOT_LOCAL") or "").strip()
            if not file_root:
                flash("FILE_ROOT_LOCAL is not configured; compiled ZIP will only include the input sheet and summary.")
            zip_bytes, missing = build_excel_compile_zip(
                rows,
                input_filename=up.filename,
                input_bytes=raw,
                file_root=file_root,
            )

            out_name = "excelcompile_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f") + ".zip"
            out_path = os.path.join(temp_root, out_name)
            with open(out_path, "wb") as f:
                f.write(zip_bytes)
        finally:
            try:
                os.remove(temp_input)
            except Exception:
                pass

        return render_template("tools/excel_compile.html", upload=True, filepath=out_name, missing=missing)

    return render_template("tools/excel_compile.html", upload=False, filepath=None, missing=[])


@bp.get("/excelcompile/download/<path:filename>")
@login_required
def excel_compile_download(filename):
    root = os.path.join(current_app.instance_path, "excelcompile")
    target = os.path.abspath(os.path.join(root, filename))
    if not target.startswith(os.path.abspath(root) + os.sep):
        abort(404)
    if not os.path.isfile(target):
        abort(404)
    return send_file(target, as_attachment=True, download_name=os.path.basename(target))
