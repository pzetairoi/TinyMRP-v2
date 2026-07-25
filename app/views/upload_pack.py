from __future__ import annotations

from typing import List

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.extensions import csrf
from app.models.extra_file import PartExtraFile
from app.services.authorization import has_permission
from app.services.extra_files import (
    extra_file_url_for,
    extra_rel_path,
    purge_associated_file,
    rev_from_token,
    store_associated_uploads,
    validated_upload_filename,
)
from app.services.file_security import (
    associated_file_category_allowed,
    associated_file_path_allowed,
    exact_file_part,
)
from app.services.part_norm import clean_pn, clean_rev
from app.services.import_zip import normalize_override_mode
from app.services.upload_pack import import_upload_pack, released_upload_targets
from app.views.api_helpers import add_datetime_fields


bp = Blueprint("upload_pack_api", __name__, url_prefix="/api")


def _extra_file_payload(ef: PartExtraFile) -> dict:
    payload = {
        "id": str(ef.id),
        "pn": ef.part_number,
        "rev": ef.revision or "",
        "original_name": ef.original_name,
        "rel_path": ef.rel_path,
        "size": ef.size,
        "mime": ef.mime,
        "sha256": ef.sha256,
        "label": ef.label or "",
        "uploaded_by": ef.uploaded_by or "",
        "url": extra_file_url_for(ef),
    }
    add_datetime_fields(payload, "uploaded_at", ef.uploaded_at)
    return payload


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in ("1", "true", "yes", "on")


def _uploaded_by() -> str:
    return (getattr(current_user, "email", None) or str(getattr(current_user, "id", ""))).strip()


@bp.post("/upload/pack")
@csrf.exempt
@login_required
def upload_pack():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "file required"}), 400
    max_zip_mb = int(current_app.config.get("UPLOAD_PACK_MAX_ZIP_MB") or 0)
    if max_zip_mb and request.content_length:
        if request.content_length > max_zip_mb * 1024 * 1024:
            return jsonify({"error": "file too large"}), 413
    filename = secure_filename(f.filename)
    dry_run = _parse_bool(request.form.get("dry_run") or request.args.get("dry_run"))
    strict = _parse_bool(request.form.get("strict_structure") or request.args.get("strict_structure"))
    override_mode = normalize_override_mode(
        request.form.get("override_mode")
        or request.args.get("override_mode")
        or "unless_existing_approved"
    )
    required_permission = (
        "imports.preview"
        if dry_run
        else (
            "imports.execute_approved"
            if override_mode in {"always", "approved_only"}
            else "imports.execute_low_risk"
        )
    )
    if not has_permission(current_user, required_permission):
        return jsonify({"error": "forbidden"}), 403
    can_override_approved = has_permission(
        current_user,
        "imports.override_approved",
    )
    if override_mode in {"always", "approved_only"} and not can_override_approved:
        return jsonify({"error": "forbidden"}), 403
    allow_extra = bool(current_app.config.get("EXTRA_FILES_ALLOWED", True))
    file_bytes = f.read()
    try:
        preflight = import_upload_pack(
            file_bytes,
            filename,
            uploaded_by=_uploaded_by(),
            dry_run=True,
            strict_structure=strict,
            allow_extra=allow_extra,
            override_mode=override_mode,
        )
        released_targets = released_upload_targets(preflight)
        if released_targets and not can_override_approved:
            return (
                jsonify(
                    {
                        "error": "forbidden",
                        "detail": "import would modify approved or released parts",
                    }
                ),
                403,
            )
        result = (
            preflight
            if dry_run
            else import_upload_pack(
                file_bytes,
                filename,
                uploaded_by=_uploaded_by(),
                dry_run=False,
                strict_structure=strict,
                allow_extra=allow_extra,
                override_mode=override_mode,
            )
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        try:
            current_app.logger.exception("Upload pack failed: %s", filename)
        except Exception:
            pass
        return (
            jsonify(
                {
                    "error": "upload failed",
                    "detail": str(exc),
                    "exception_type": type(exc).__name__,
                }
            ),
            500,
        )
    try:
        from app.services.audit import log_action

        def metric_count(value):
            if isinstance(value, (list, tuple, set, dict)):
                return len(value)
            try:
                return int(value or 0)
            except (TypeError, ValueError):
                return 0

        log_action(
            "upload.pack",
            resource_type="import",
            resource=filename,
            meta={
                "parts_imported": metric_count(result.get("parts_imported") or result.get("imported_parts") or result.get("parts")),
                "files_uploaded": metric_count(result.get("files_uploaded") or result.get("file_count") or result.get("files")),
                "dry_run": dry_run,
            },
        )
    except Exception:
        pass
    return jsonify(result)


@bp.get("/parts/<path:pn>/<path:rev>/extra")
@login_required
def list_extra_files(pn: str, rev: str):
    pn_clean = clean_pn(pn)
    rev_clean = clean_rev(rev_from_token(rev))
    if not pn_clean:
        return jsonify({"error": "pn required"}), 400
    if exact_file_part(current_user, pn_clean, rev_clean) is None:
        return jsonify({"error": "not found"}), 404

    rows = []
    for ef in (
        PartExtraFile.objects(part_number__iexact=pn_clean, revision__iexact=rev_clean)
        .order_by("-uploaded_at")
        .only(
            "part_number",
            "revision",
            "original_name",
            "rel_path",
            "size",
            "mime",
            "sha256",
            "label",
            "uploaded_by",
            "uploaded_at",
        )
    ):
        if (
            not associated_file_category_allowed(current_user, ef)
            or not associated_file_path_allowed(ef)
        ):
            continue
        rows.append(_extra_file_payload(ef))
    try:
        from app.services.audit import log_action

        log_action(
            "file.list",
            resource_type="part",
            resource=f"{pn_clean}:{rev_clean}",
            meta={"associated_files": len(rows)},
        )
    except Exception:
        pass
    return jsonify(rows)


@bp.post("/parts/<path:pn>/<path:rev>/extra")
@csrf.exempt
@login_required
def upload_extra_files(pn: str, rev: str):
    if not current_app.config.get("EXTRA_FILES_ALLOWED", True):
        return jsonify({"error": "extra files disabled"}), 403
    pn_clean = clean_pn(pn)
    rev_clean = clean_rev(rev_from_token(rev))
    if not pn_clean:
        return jsonify({"error": "pn required"}), 400

    files = request.files.getlist("file")
    if not files:
        files = list(request.files.values())
    if not files:
        return jsonify({"error": "file required"}), 400

    max_files = int(current_app.config.get("UPLOAD_PACK_MAX_FILES") or 0)
    if max_files and len(files) > max_files:
        return jsonify({"error": "too many files"}), 413

    try:
        targets = []
        for upload in files:
            filename = validated_upload_filename(getattr(upload, "filename", ""))
            rel_path = extra_rel_path(pn_clean, rev_clean, filename)
            existing = PartExtraFile.objects(
                part_number__iexact=pn_clean,
                revision__iexact=rev_clean,
                rel_path=rel_path,
            ).first()
            targets.append(existing)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    requires_add = any(record is None for record in targets)
    requires_replace = any(record is not None for record in targets)
    required = []
    if requires_add:
        required.append("files.add")
    if requires_replace:
        required.append("files.replace")
    if not required or any(
        exact_file_part(
            current_user,
            pn_clean,
            rev_clean,
            permission=permission,
            mutable=True,
        )
        is None
        for permission in required
    ):
        return jsonify({"error": "not found"}), 404

    max_file_mb = int(current_app.config.get("UPLOAD_PACK_MAX_FILE_MB") or 0)
    max_bytes = max_file_mb * 1024 * 1024 if max_file_mb else 0
    uploaded_by = _uploaded_by()
    try:
        records = store_associated_uploads(
            files,
            part_number=pn_clean,
            revision=rev_clean,
            uploaded_by=uploaded_by,
            max_bytes=max_bytes,
        )
    except ValueError as exc:
        status = 413 if str(exc) == "file too large" else 400
        return jsonify({"error": str(exc)}), status
    except Exception:
        return jsonify({"error": "upload failed"}), 500
    created: List[dict] = [_extra_file_payload(record) for record in records]
    errors: List[str] = []

    try:
        from app.services.audit import log_action

        log_action(
            "upload.extra_files",
            resource_type="part",
            resource=f"{pn_clean}:{rev_clean}",
            meta={
                "files_uploaded": len(created),
                "files_added": sum(record is None for record in targets),
                "files_replaced": sum(record is not None for record in targets),
                "logical_file_ids": [f"extra:{record.id}" for record in records],
                "errors": len(errors),
            },
        )
    except Exception:
        pass
    return jsonify({"files": created, "errors": errors})


@bp.delete("/parts/<path:pn>/<path:rev>/extra/<file_id>")
@csrf.exempt
@login_required
def delete_extra_file(pn: str, rev: str, file_id: str):
    pn_clean = clean_pn(pn)
    rev_clean = clean_rev(rev_from_token(rev))
    if not pn_clean:
        return jsonify({"error": "pn required"}), 400
    if (
        exact_file_part(
            current_user,
            pn_clean,
            rev_clean,
            permission="files.purge",
        )
        is None
    ):
        return jsonify({"error": "not found"}), 404

    ef = PartExtraFile.objects(id=file_id).first()
    if not ef:
        return jsonify({"error": "not found"}), 404
    if (
        (ef.part_number or "").strip().lower() != pn_clean.lower()
        or (ef.revision or "") != rev_clean
    ):
        return jsonify({"error": "not found"}), 404

    try:
        from app.services.audit import log_action

        log_action(
            "file.purge.requested",
            resource_type="file",
            resource=f"extra:{ef.id}",
            meta={"part": f"{pn_clean}:{rev_clean}"},
        )
    except Exception:
        pass
    try:
        purge_associated_file(ef)
    except Exception:
        return jsonify({"error": "delete failed"}), 500
    try:
        from app.services.audit import log_action

        log_action(
            "file.purge.completed",
            resource_type="file",
            resource=f"extra:{file_id}",
            meta={"part": f"{pn_clean}:{rev_clean}"},
        )
    except Exception:
        pass
    return jsonify({"ok": True})
