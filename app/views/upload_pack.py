from __future__ import annotations
import logging
import json
from typing import List
from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from app.extensions import csrf
from app.services.authorization import require_permission
from app.models.extra_file import PartExtraFile
from app.services.authorization import (
    effective_permissions,
    has_permission,
    relationship_part_pairs,
)
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
from app.services.upload_pack import (
    IMPORT_PERMISSIONS,
    ImportPermissionError,
    ImportScopeError,
    import_upload_pack,
)
from app.views.api_helpers import add_datetime_fields

logger = logging.getLogger(__name__)
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
def _import_options() -> dict:
    source = request.form if request.form else request.args
    options = {
        name: source.get(name) or None
        for name in ("data_mode", "bom_mode", "file_mode", "approval_mode")
    }
    # Operator picks for clashing part identities, posted as JSON so a pack with
    # several clashes needs one field rather than one per part.
    raw = source.get("duplicate_choices") or ""
    try:
        parsed = json.loads(raw) if raw else {}
    except ValueError:
        parsed = {}
    options["duplicate_choices"] = parsed if isinstance(parsed, dict) else {}
    return options
def _mutable_scope_check(pairs):
    """Return the exact requested pairs outside the caller's part scope.

    Globally scoped users may mutate any planned pair; relationship-scoped
    users are limited to their exact derived part/revision set.
    """
    allowed = relationship_part_pairs(current_user)
    if allowed is None:
        return []
    allowed_folded = {
        (str(pn).strip().casefold(), str(rev or "").strip().casefold())
        for pn, rev in allowed
    }
    return [
        (pn, rev)
        for pn, rev in pairs
        if (str(pn).strip().casefold(), str(rev or "").strip().casefold())
        not in allowed_folded
    ]
@bp.get("/import/capabilities")
@login_required
def import_capabilities():
    """Lightweight effective import capabilities for the Upload Pack UI."""
    return jsonify(
        {
            "imports": {
                permission: has_permission(current_user, permission)
                for permission in sorted(IMPORT_PERMISSIONS)
            }
        }
    )
def _recovery_note_for_failed_import(uploader: str) -> dict:
    """What happened to the data after an import failed, in plain words.

    The journal records whether the compensating rollback ran and whether
    anything was left needing a human. Without surfacing it, an operator sees
    an exception and cannot tell a clean abort from a half-applied import -
    which is the difference between retrying and reconciling by hand.
    """
    try:
        from app.models.import_journal import ImportJournal

        # The importer owns the operation id, so find this uploader's most
        # recent run rather than threading it back out through the exception.
        entry = (
            ImportJournal.objects(uploaded_by=uploader)
            .order_by("-started_at")
            .first()
        )
        if entry is None or entry.status == "committed":
            return {}
        followup = list(entry.manual_followup or [])
        rolled_back = list(entry.rollback_actions or [])
        if entry.status == "rolled_back" and not followup:
            summary = (
                "Nothing was kept. The import was undone completely"
                + (f" ({len(rolled_back)} change(s) reversed)" if rolled_back else "")
                + ". You can safely fix the cause and try again."
            )
        elif followup:
            summary = (
                "This import was only partly undone and needs checking by hand. "
                "See the items listed under manual_followup."
            )
        else:
            summary = (
                "The import did not complete. Its state is recorded under "
                f"operation {entry.operation_id}."
            )
        return {
            "operation_id": entry.operation_id,
            "recovery_status": entry.status,
            "recovery_summary": summary,
            "manual_followup": followup,
        }
    except Exception:
        # Never let the explanation replace the original error.
        logger.exception("could not build a recovery note for the last import by %s", uploader)
        return {}


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
    allow_extra = bool(current_app.config.get("EXTRA_FILES_ALLOWED", True))
    file_bytes = f.read()
    try:
        result = import_upload_pack(
            file_bytes,
            filename,
            uploaded_by=_uploaded_by(),
            dry_run=dry_run,
            strict_structure=strict,
            allow_extra=allow_extra,
            actor_permissions=set(effective_permissions(current_user)),
            scope_check=_mutable_scope_check,
            **_import_options(),
        )
    except ImportPermissionError as exc:
        return (
            jsonify(
                {
                    "error": "forbidden",
                    "detail": str(exc),
                    "missing_permissions": exc.missing_permissions,
                }
            ),
            403,
        )
    except ImportScopeError as exc:
        return (
            jsonify(
                {
                    "error": "forbidden",
                    "detail": str(exc),
                    "denied_parts": [
                        {"pn": pn, "rev": rev} for pn, rev in exc.denied_pairs
                    ],
                }
            ),
            403,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        try:
            current_app.logger.exception("Upload pack failed: %s", filename)
        except Exception:
            pass
        # Tell the operator what STATE they are in, not just what threw.
        # A bare "cross-store file commit failed at <part>" leaves them unable
        # to answer the only question that matters - did any of this land? -
        # and the journal already knows. Reported here so they do not have to
        # go looking for an API to ask.
        recovery = _recovery_note_for_failed_import(_uploaded_by())
        return (
            jsonify(
                {
                    "error": "upload failed",
                    "detail": str(exc),
                    "exception_type": type(exc).__name__,
                    **recovery,
                }
            ),
            500,
        )
    try:
        from app.services.audit import log_action
        metrics = result.get("metrics") or {}
        log_action(
            "upload.pack",
            resource_type="import",
            resource=filename,
            meta={
                "parts_created": int(metrics.get("parts_created") or 0),
                "parts_updated": int(metrics.get("parts_updated") or 0),
                "files_uploaded": int(metrics.get("files_written") or 0),
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


def _journal_row(entry) -> dict:
    """Serialise one journal entry for an operator.

    Deliberately includes the failure detail and the manual-follow-up notes:
    the whole point of the journal is that a failed import can be reconciled,
    and that is impossible if the endpoint hides why it failed.
    """
    return {
        "operation_id": entry.operation_id,
        "status": entry.status,
        "stage": entry.stage,
        "started_at": entry.started_at.isoformat() if entry.started_at else "",
        "finished_at": entry.finished_at.isoformat() if entry.finished_at else "",
        "uploaded_by": entry.uploaded_by,
        "planned_parts": entry.planned_parts,
        "planned_files": entry.planned_files,
        "parts_created": entry.parts_created,
        "parts_updated": entry.parts_updated,
        "links_created": entry.links_created,
        "files_written": entry.files_written,
        "touched_parts": [item.replace("\x1f", ":") for item in (entry.touched_parts or [])],
        "rollback_actions": list(entry.rollback_actions or []),
        "manual_followup": list(entry.manual_followup or []),
        "error": entry.error,
    }


@bp.get("/import/operations")
@login_required
@require_permission("system.maintenance")
def import_operations():
    """List recent import operations (IMPORT-ATOMIC-01).

    The acceptance criterion is that operators can diagnose and reconcile every
    import. The journal has always been queryable in Mongo; this makes it
    reachable without shell access to the database.

    Defaults to failures first, because those are the ones needing action.
    """
    from app.models.import_journal import ImportJournal

    status = (request.args.get("status") or "").strip()
    try:
        limit = max(1, min(int(request.args.get("limit") or 50), 200))
    except (TypeError, ValueError):
        limit = 50

    query = ImportJournal.objects
    if status:
        query = query.filter(status=status)

    rows = [_journal_row(entry) for entry in query.order_by("-started_at").limit(limit)]
    unresolved = ImportJournal.objects(status__in=["failed", "rolled_back"]).count()
    return jsonify({"ok": True, "operations": rows, "unresolved_count": unresolved})


@bp.get("/import/operations/<operation_id>")
@login_required
@require_permission("system.maintenance")
def import_operation(operation_id: str):
    from app.models.import_journal import ImportJournal

    entry = ImportJournal.objects(operation_id=operation_id).first()
    if not entry:
        return jsonify({"ok": False, "error": {"message": "Unknown operation id."}}), 404
    return jsonify({"ok": True, "operation": _journal_row(entry)})
