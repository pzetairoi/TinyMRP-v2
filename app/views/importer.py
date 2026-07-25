# app/views/importer.py
from flask import Blueprint, abort, current_app, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from app.extensions import csrf
from app.services.authorization import has_permission, require_permission
from app.services.import_zip import import_bom_zip, normalize_override_mode
from app.services.upload_pack import import_upload_pack, released_upload_targets

bp = Blueprint("importer", __name__, url_prefix="/import")

@bp.get("/")
@login_required
@require_permission("imports.preview")
def upload_form():
    return redirect("/ui/upload-pack")

@bp.post("/")
@csrf.exempt  # keep it simple; remove if you wire a WTForm with CSRF token
@login_required
def upload_post():
    f = request.files.get("file")
    if not f or not f.filename:
        flash("Please choose a .zip file.", "warning")
        return redirect(url_for("importer.upload_form"))
    max_zip_mb = int(current_app.config.get("UPLOAD_PACK_MAX_ZIP_MB") or 0)
    if max_zip_mb and request.content_length:
        if request.content_length > max_zip_mb * 1024 * 1024:
            flash("File too large.", "warning")
            return redirect(url_for("importer.upload_form"))
    fn = secure_filename(f.filename)
    override_mode = normalize_override_mode(
        request.form.get("override_mode")
        or request.args.get("override_mode")
        or "unless_existing_approved"
    )
    if not has_permission(current_user, "imports.execute_low_risk"):
        abort(403)
    can_override = has_permission(current_user, "imports.override_approved")
    if override_mode in {"always", "approved_only"} and not can_override:
        abort(403)
    file_bytes = f.read()
    try:
        preflight = import_upload_pack(
            file_bytes,
            fn,
            dry_run=True,
            allow_extra=False,
            override_mode=override_mode,
        )
        if released_upload_targets(preflight) and not can_override:
            abort(403)
        result = import_bom_zip(
            file_bytes,
            fn,
            seed_tag="upload",
            override_mode=override_mode,
        )
    except ValueError as exc:
        flash(f"Import failed: {exc}", "danger")
        return redirect(url_for("importer.upload_form"))
    except Exception as exc:
        if getattr(exc, "code", None) == 403:
            raise
        try:
            current_app.logger.exception("Import failed: %s", fn)
        except Exception:
            pass
        flash(f"Import failed: {exc}", "danger")
        return redirect(url_for("importer.upload_form"))

    err_count = len(result.get("errors") or [])
    warn_count = len(result.get("warnings") or [])
    thumbs = result.get('thumbnails_generated') or result.get('thumbnails_built') or 0
    flash(
        f"Imported {result['zip']} - root={result['root']} - parts+{result['parts_created']} links+{result['links_created']} - thumbs={thumbs} - errors={err_count} warnings={warn_count}",
        "warning" if err_count else ("info" if warn_count else "success"),
    )
    return render_template("import/result.html", result=result)

# Optional: JSON API endpoint for programmatic uploads
@bp.post("/api")
@csrf.exempt
@login_required
def upload_api():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "file required"}), 400
    max_zip_mb = int(current_app.config.get("UPLOAD_PACK_MAX_ZIP_MB") or 0)
    if max_zip_mb and request.content_length:
        if request.content_length > max_zip_mb * 1024 * 1024:
            return jsonify({"error": "file too large"}), 413
    fn = secure_filename(f.filename)
    override_mode = normalize_override_mode(
        request.form.get("override_mode")
        or request.args.get("override_mode")
        or "unless_existing_approved"
    )
    if not has_permission(current_user, "imports.execute_low_risk"):
        return jsonify({"error": "forbidden"}), 403
    can_override = has_permission(current_user, "imports.override_approved")
    if override_mode in {"always", "approved_only"} and not can_override:
        return jsonify({"error": "forbidden"}), 403
    file_bytes = f.read()
    try:
        preflight = import_upload_pack(
            file_bytes,
            fn,
            dry_run=True,
            allow_extra=False,
            override_mode=override_mode,
        )
        if released_upload_targets(preflight) and not can_override:
            return jsonify({"error": "forbidden"}), 403
        result = import_bom_zip(
            file_bytes,
            fn,
            seed_tag="upload-api",
            override_mode=override_mode,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        try:
            current_app.logger.exception("Import API failed: %s", fn)
        except Exception:
            pass
        return jsonify({"error": "import failed", "detail": str(exc), "exception_type": type(exc).__name__}), 500
    return jsonify(result)
