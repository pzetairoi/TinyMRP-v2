from flask import Blueprint, render_template, request, send_file, current_app, redirect, url_for, abort, flash
import os
import tempfile
from io import BytesIO
from datetime import datetime, timezone
from flask_login import login_required
from app.services.acl import permissions_required
from app.services.filenames import build_output_name
from app.services.timezone_utils import format_display_ts, utc_now


def _excel_compile_root() -> str:
    # instance_path is not writable in the hardened (read-only) container;
    # the tmpfs-backed system temp dir always is.
    root = os.path.join(tempfile.gettempdir(), "tinymrp_excelcompile")
    os.makedirs(root, exist_ok=True)
    return root

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
                        'modified': format_display_ts(datetime.fromtimestamp(mtime, tz=timezone.utc), fmt="%Y-%m-%d %H:%M %Z"),
                        'mtime': mtime,
                    })
    except Exception:
        pass
    items.sort(key=lambda item: item.get('mtime') or 0, reverse=True)
    return items


@bp.get("/")
@login_required
@permissions_required("tools.view")
def tools_index():
    files = _static_tools()
    addin_files = _addin_installers()
    return render_template("tools/index.html", files=files, addin_files=addin_files)


@bp.get("/addin/latest")
@login_required
@permissions_required("tools.view")
def addin_latest():
    addin_files = _addin_installers()
    if not addin_files:
        return redirect(url_for('tools.tools_index'))
    target = os.path.join(_addin_root(), addin_files[0]['name'])
    if not os.path.isfile(target):
        return redirect(url_for('tools.tools_index'))
    return send_file(target, as_attachment=True, download_name=os.path.basename(target))


@bp.get("/addin/<path:filename>")
@login_required
@permissions_required("tools.view")
def addin_download(filename):
    root = _addin_root()
    target = os.path.abspath(os.path.join(root, filename))
    if not target.startswith(root + os.sep):
        abort(404)
    if not os.path.isfile(target):
        abort(404)
    return send_file(target, as_attachment=True, download_name=os.path.basename(target))


def _excel_compile_options():
    from app.services.field_config import get_field_config
    config = get_field_config()
    ctx = config.get("contexts", {}).get("excel_bom", {})
    field_defs = {f["id"]: f for f in config.get("fields", [])}
    allowed = ctx.get("allowed_field_ids") or []
    required = set(ctx.get("required_field_ids") or [])
    default_ids = set(ctx.get("default_field_ids") or [])
    excel_fields = [
        {
            "id": fid,
            "label": field_defs.get(fid, {}).get("label") or fid.replace("_", " ").title(),
            "required": fid in required,
            "checked": fid in default_ids or fid in required,
        }
        for fid in allowed
    ]
    meta = current_app.config.get("PROCESS_META", {}) or {}
    processes = sorted([k for k in meta.keys() if not str(k).startswith("_")])

    from app.models.artifact import PartFile
    file_types = sorted([g for g in PartFile.objects().distinct("ext_group") if g])

    return excel_fields, processes, file_types


def _default_compile_title() -> str:
    return f"BOM {format_display_ts(utc_now(), fmt='%Y-%m-%d')}"


@bp.route("/excelcompile", methods=["GET", "POST"])
@login_required
@permissions_required("tools.view")
def excel_compile():
    excel_fields, processes, file_types_available = _excel_compile_options()
    default_title = _default_compile_title()

    if request.method == "POST":
        up = request.files.get("file")
        if not up or not up.filename:
            flash("Select an Excel file to upload.")
            return render_template("tools/excel_compile.html", upload=False, filepath=None, missing=[], excel_fields=excel_fields, processes=processes, default_title=default_title, file_types=file_types_available)

        ext = os.path.splitext(up.filename)[1].lower()
        if ext != ".xlsx":
            flash("Only .xlsx files are supported.")
            return render_template("tools/excel_compile.html", upload=False, filepath=None, missing=[], excel_fields=excel_fields, processes=processes, default_title=default_title, file_types=file_types_available)

        max_bytes = int(current_app.config.get("EXCEL_COMPILE_MAX_BYTES") or 0)
        if max_bytes and request.content_length and request.content_length > max_bytes:
            flash("File too large for compile.")
            return render_template("tools/excel_compile.html", upload=False, filepath=None, missing=[], excel_fields=excel_fields, processes=processes, default_title=default_title, file_types=file_types_available)

        raw = up.read()
        if not raw:
            flash("Uploaded file was empty.")
            return render_template("tools/excel_compile.html", upload=False, filepath=None, missing=[], excel_fields=excel_fields, processes=processes, default_title=default_title, file_types=file_types_available)

        # Save a temporary copy for parsing (tmpfs-backed, writable under the hardened container)
        temp_root = _excel_compile_root()
        temp_input = os.path.join(temp_root, "upload_" + utc_now().strftime("%Y%m%d_%H%M%S_%f") + ".xlsx")
        with open(temp_input, "wb") as f:
            f.write(raw)

        def _fbool(name: str, default: bool = False) -> bool:
            if name not in request.form:
                return default
            return request.form.get(name) in ("on", "1", "true", "True")

        docpack_kwargs = dict(
            file_groups=request.form.getlist("file_types") or None,
            process_mode="selected" if request.form.get("process_mode") == "selected" else "all",
            processes=request.form.getlist("processes") or None,
            classified_filter=request.form.get("classified_filter") or "show",
            expand_subassemblies=_fbool("expand_subassemblies", True),
            want_excel_bom=_fbool("want_excel_bom", True),
            excel_all_fields=_fbool("excel_all_fields", False),
            excel_field_ids=request.form.getlist("excel_field_ids") or None,
            want_pdf_binder=_fbool("want_pdf_binder", False),
            want_index_pdf=_fbool("want_index_pdf", False),
            want_visual_list=_fbool("want_visual_list", False),
            want_hardware_summary=_fbool("want_hardware_summary", False),
            want_cover_page=_fbool("want_cover_page", False),
            want_whereused_report=_fbool("want_whereused_report", False),
            binder_add_cover=_fbool("binder_add_cover", True),
            binder_add_index=_fbool("binder_add_index", True),
            binder_add_visual_list=_fbool("binder_add_visual_list", True),
            binder_add_whereused=_fbool("binder_add_whereused", False),
            binder_add_hardware_summary=_fbool("binder_add_hardware_summary", True),
            binder_add_datasheets=_fbool("binder_add_datasheets", False),
            binder_page_numbers=_fbool("binder_page_numbers", True),
            binder_include_flat_patterns=_fbool("binder_include_flat_patterns", False),
            stamp_quote=_fbool("stamp_quote", False),
            stamp_confidential=_fbool("stamp_confidential", False),
            stamp_approved=_fbool("stamp_approved", False),
            stamp_wip=_fbool("stamp_wip", False),
            stamp_inprogress=_fbool("stamp_inprogress", False),
            title=(request.form.get("title") or "").strip() or default_title,
        )

        from app.services.excel_compile import parse_compile_excel, build_excel_compile_zip
        try:
            rows = parse_compile_excel(temp_input)
            if not rows:
                flash("No valid rows found. Ensure the sheet is named COMPILE and has a PartNumber column.")
                return render_template("tools/excel_compile.html", upload=False, filepath=None, missing=[], excel_fields=excel_fields, processes=processes, default_title=default_title, file_types=file_types_available)

            file_root = (current_app.config.get("FILE_ROOT_LOCAL") or "").strip()
            if not file_root:
                flash("FILE_ROOT_LOCAL is not configured; compiled ZIP will only include the input sheet and summary.")
            zip_bytes, missing = build_excel_compile_zip(
                rows,
                input_filename=up.filename,
                input_bytes=raw,
                file_root=file_root,
                **docpack_kwargs,
            )

            name_base = docpack_kwargs["title"]
            out_name = build_output_name(name_base, "zip", max_len=96, include_time=False, now=utc_now())
            out_path = os.path.join(temp_root, out_name)
            if os.path.exists(out_path):
                out_name = build_output_name(name_base, "zip", max_len=96, include_time=True, now=utc_now())
                out_path = os.path.join(temp_root, out_name)
            with open(out_path, "wb") as f:
                f.write(zip_bytes)
        finally:
            try:
                os.remove(temp_input)
            except Exception:
                pass

        return render_template("tools/excel_compile.html", upload=True, filepath=out_name, missing=missing, excel_fields=excel_fields, processes=processes, default_title=default_title, file_types=file_types_available)

    return render_template("tools/excel_compile.html", upload=False, filepath=None, missing=[], excel_fields=excel_fields, processes=processes, default_title=default_title, file_types=file_types_available)


@bp.get("/excelcompile/download/<path:filename>")
@login_required
@permissions_required("tools.view")
def excel_compile_download(filename):
    root = _excel_compile_root()
    target = os.path.abspath(os.path.join(root, filename))
    if not target.startswith(os.path.abspath(root) + os.sep):
        abort(404)
    if not os.path.isfile(target):
        abort(404)
    return send_file(target, as_attachment=True, download_name=os.path.basename(target))
