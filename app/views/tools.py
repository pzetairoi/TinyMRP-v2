from flask import Blueprint, render_template, request, send_file, current_app, redirect, url_for, abort, flash
import os
import secrets
import tempfile
from io import BytesIO
from datetime import datetime, timezone
from flask_login import current_user, login_required
from app.services.acl import permissions_required
from app.services.authorization import has_permission, require_permission
from app.services.export_artifacts import (
    load_export_artifact,
    store_export_artifact,
)
from app.services.export_security import (
    ExportSecurityError,
    exact_bom_pairs,
    preflight_export_plan,
)
from app.services.filenames import build_output_name
from app.services.audit import log_action
from app.services.timezone_utils import format_display_ts, utc_now


def _excel_compile_root() -> str:
    # instance_path is not writable in the hardened (read-only) container;
    # the tmpfs-backed system temp dir always is.
    root = os.path.join(tempfile.gettempdir(), "tinymrp_excelcompile")
    os.makedirs(root, exist_ok=True)
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass
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

    file_types = [
        "png",
        "pdf",
        "dxf",
        "step",
        "edr",
        "3mf",
        "ply",
        "stl",
        "datasheet",
    ]

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
        if not has_permission(current_user, "exports.run"):
            abort(403)
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
        stamp = secrets.token_hex(16)
        temp_input = os.path.join(temp_root, f"upload_{stamp}.xlsx")
        with open(temp_input, "wb") as f:
            f.write(raw)

        temp_thumb = None
        thumb_up = request.files.get("thumbnail")
        if thumb_up and thumb_up.filename:
            thumb_ext = os.path.splitext(thumb_up.filename)[1].lower()
            if thumb_ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                try:
                    os.remove(temp_input)
                except OSError:
                    pass
                flash("Top-level image must be PNG, JPEG, GIF, or WEBP.")
                return render_template("tools/excel_compile.html", upload=False, filepath=None, missing=[], excel_fields=excel_fields, processes=processes, default_title=default_title, file_types=file_types_available)
            thumb_raw = thumb_up.read()
            if thumb_raw:
                temp_thumb = os.path.join(temp_root, f"thumb_{stamp}{thumb_ext}")
                with open(temp_thumb, "wb") as f:
                    f.write(thumb_raw)

        def _fbool(name: str, default: bool = False) -> bool:
            # A browser omits an unchecked checkbox from the POST body entirely,
            # so "absent" always means "unchecked" for form-submitted checkboxes
            # -- never fall back to True here, or unchecking a pre-checked box
            # (e.g. "Expand sub-assemblies") silently has no effect. Boxes that
            # should start checked get that from the template's `checked`
            # attribute, not from this default.
            if name not in request.form:
                return default
            return request.form.get(name) in ("on", "1", "true", "True")

        docpack_kwargs = dict(
            file_groups=request.form.getlist("file_types") or None,
            process_mode="selected" if request.form.get("process_mode") == "selected" else "all",
            processes=request.form.getlist("processes") or None,
            classified_filter=request.form.get("classified_filter") or "show",
            expand_subassemblies=_fbool("expand_subassemblies", False),
            want_excel_bom=_fbool("want_excel_bom", False),
            excel_all_fields=_fbool("excel_all_fields", False),
            excel_field_ids=request.form.getlist("excel_field_ids") or None,
            want_pdf_binder=_fbool("want_pdf_binder", False),
            want_index_pdf=_fbool("want_index_pdf", False),
            want_visual_list=_fbool("want_visual_list", False),
            want_hardware_summary=_fbool("want_hardware_summary", False),
            want_cover_page=_fbool("want_cover_page", False),
            want_markup_files=_fbool("want_markup_files", False),
            want_markup_report=_fbool("want_markup_report", False),
            binder_add_cover=_fbool("binder_add_cover", False),
            binder_add_index=_fbool("binder_add_index", False),
            binder_add_visual_list=_fbool("binder_add_visual_list", False),
            binder_add_hardware_summary=_fbool("binder_add_hardware_summary", False),
            binder_add_datasheets=_fbool("binder_add_datasheets", False),
            binder_add_markups=_fbool("binder_add_markups", False),
            binder_page_numbers=_fbool("binder_page_numbers", False),
            binder_include_flat_patterns=_fbool("binder_include_flat_patterns", False),
            stamp_quote=_fbool("stamp_quote", False),
            stamp_confidential=_fbool("stamp_confidential", False),
            stamp_approved=_fbool("stamp_approved", False),
            stamp_wip=_fbool("stamp_wip", False),
            stamp_inprogress=_fbool("stamp_inprogress", False),
            title=(request.form.get("title") or "").strip() or default_title,
            description=(request.form.get("description") or "").strip(),
            thumbnail_path=temp_thumb,
        )

        from app.services.excel_compile import parse_compile_excel, build_excel_compile_zip
        try:
            rows = parse_compile_excel(temp_input)
            if not rows:
                flash("No valid rows found. Ensure the sheet is named COMPILE and has a PartNumber column.")
                return render_template("tools/excel_compile.html", upload=False, filepath=None, missing=[], excel_fields=excel_fields, processes=processes, default_title=default_title, file_types=file_types_available)

            from app.models.part import Part

            exact_parts = []
            for row in rows:
                part = Part.objects(
                    part_number__iexact=row.part_number,
                    revision__iexact=row.revision,
                ).first()
                if part:
                    exact_parts.append(part)
            planned_pairs: set[tuple[str, str]] = set()
            expand = bool(docpack_kwargs["expand_subassemblies"])
            for part in exact_parts:
                if expand:
                    planned_pairs.update(
                        exact_bom_pairs(
                            part.part_number,
                            part.revision,
                            full=True,
                        )
                    )
                else:
                    planned_pairs.add(
                        (part.part_number, part.revision or "")
                    )
            requested_groups = docpack_kwargs["file_groups"] or [
                "pdf",
                "dxf",
                "step",
                "datasheet",
            ]
            include_markups = bool(
                docpack_kwargs["want_markup_files"]
                or docpack_kwargs["want_markup_report"]
                or docpack_kwargs["binder_add_markups"]
            )
            if planned_pairs:
                preflight_export_plan(
                    current_user,
                    planned_pairs,
                    require_bom=expand,
                    include_files=True,
                    file_groups=set(requested_groups),
                    include_markups=include_markups,
                )

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
            artifact_token = store_export_artifact(
                zip_bytes,
                owner_id=getattr(current_user, "id", ""),
                display_name=out_name,
                pairs=sorted(planned_pairs),
                file_groups=sorted(requested_groups),
                include_markups=include_markups,
                require_bom=expand,
            )
            out_name = artifact_token
            log_action(
                "excel_compile.export",
                resource_type="parts",
                resource="compile",
                meta={
                    "part_count": len(planned_pairs),
                    "included_categories": "parts,bom,files",
                    "financial_content": False,
                    "file_content": True,
                    "outcome": "success",
                },
            )
        except ExportSecurityError:
            abort(403)
        finally:
            try:
                os.remove(temp_input)
            except Exception:
                pass
            if temp_thumb:
                try:
                    os.remove(temp_thumb)
                except Exception:
                    pass

        return render_template("tools/excel_compile.html", upload=True, filepath=out_name, missing=missing, excel_fields=excel_fields, processes=processes, default_title=default_title, file_types=file_types_available)

    return render_template("tools/excel_compile.html", upload=False, filepath=None, missing=[], excel_fields=excel_fields, processes=processes, default_title=default_title, file_types=file_types_available)


@bp.get("/excelcompile/download/<path:filename>")
@login_required
@permissions_required("tools.view")
@require_permission("exports.run")
def excel_compile_download(filename):
    try:
        target, metadata = load_export_artifact(
            filename,
            owner_id=getattr(current_user, "id", ""),
        )
        stored_pairs = [
            (str(pair[0]), str(pair[1]))
            for pair in metadata.get("pairs", [])
            if isinstance(pair, list) and len(pair) == 2
        ]
        if stored_pairs:
            preflight_export_plan(
                current_user,
                stored_pairs,
                require_bom=bool(metadata.get("require_bom", True)),
                include_files=True,
                file_groups=(
                    set(metadata["file_groups"])
                    if metadata.get("file_groups") is not None
                    else None
                ),
                include_markups=bool(metadata.get("include_markups")),
            )
    except (ExportSecurityError, ValueError):
        abort(404)
    return send_file(
        target,
        as_attachment=True,
        download_name=os.path.basename(
            str(metadata.get("display_name") or "export.zip")
        ),
    )
