from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from app.extensions import csrf
from app.services.authorization import effective_permissions, require_permission
from app.services.import_zip import DEFAULT_OVERRIDE_MODE
from app.services.upload_pack import ImportPermissionError, import_upload_pack
bp = Blueprint("importer", __name__, url_prefix="/import")
def _options():
    source = request.form if request.form else request.args
    values = {
        "override_mode": source.get("override_mode") or DEFAULT_OVERRIDE_MODE,
        **{
            name: source.get(name) or None
            for name in ("data_mode", "bom_mode", "file_mode", "approval_mode")
        },
    }
    if not source.get("override_mode") and not any(
        values[name] for name in ("data_mode", "bom_mode", "file_mode", "approval_mode")
    ):
        values.update(
            data_mode="fill_blanks",
            bom_mode="fill_if_empty",
            file_mode="add_missing",
            approval_mode="preserve",
        )
    return values
def _uploaded_file():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        raise ValueError("file required")
    limit = int(current_app.config.get("UPLOAD_PACK_MAX_ZIP_MB") or 0) * 1024 * 1024
    if limit and request.content_length and request.content_length > limit:
        raise OverflowError("file too large")
    return upload, secure_filename(upload.filename)
def _execute(seed: str):
    upload, filename = _uploaded_file()
    return (
        import_upload_pack(
            upload.read(),
            filename,
            allow_extra=False,
            seed_tag=seed,
            actor_permissions=set(effective_permissions(current_user)),
            **_options(),
        ).get("import")
        or {}
    )
@bp.get("/")
@login_required
@require_permission("imports.preview")
def upload_form():
    return redirect("/ui/upload-pack")
@bp.post("/")
@csrf.exempt
@login_required
def upload_post():
    try:
        result = _execute("upload")
    except ImportPermissionError:
        abort(403)
    except (ValueError, OverflowError) as exc:
        flash(f"Import failed: {exc}", "danger")
        return redirect(url_for("importer.upload_form"))
    except Exception as exc:
        current_app.logger.exception("Import failed")
        flash(f"Import failed: {exc}", "danger")
        return redirect(url_for("importer.upload_form"))
    errors, warnings = len(result.get("errors") or []), len(result.get("warnings") or [])
    flash(
        f"Imported {result['zip']} - root={result['root']} - parts+{result['parts_created']} "
        f"links+{result['links_created']} - errors={errors} warnings={warnings}",
        "warning" if errors else ("info" if warnings else "success"),
    )
    return render_template("import/result.html", result=result)
@bp.post("/api")
@csrf.exempt
@login_required
def upload_api():
    try:
        return jsonify(_execute("upload-api"))
    except ImportPermissionError as exc:
        return jsonify(error="forbidden", missing_permissions=exc.missing_permissions), 403
    except OverflowError as exc:
        return jsonify(error=str(exc)), 413
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception as exc:
        current_app.logger.exception("Import API failed")
        return jsonify(error="import failed", detail=str(exc), exception_type=type(exc).__name__), 500
