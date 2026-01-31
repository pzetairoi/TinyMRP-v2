from __future__ import annotations

import os
from datetime import datetime
from typing import List

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.extensions import csrf
from app.models.extra_file import PartExtraFile
from app.services.acl import (
    allowed_parts_for,
    part_is_allowed,
    permissions_required,
    require_items_view,
)
from app.services.extra_files import (
    extra_abs_path,
    extra_file_url_for,
    extra_rel_path,
    extra_root,
    guess_mime,
    hash_file,
    rev_from_token,
)
from app.services.part_norm import clean_pn, clean_rev
from app.services.upload_pack import import_upload_pack


bp = Blueprint("upload_pack_api", __name__, url_prefix="/api")


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in ("1", "true", "yes", "on")


def _uploaded_by() -> str:
    return (getattr(current_user, "email", None) or str(getattr(current_user, "id", ""))).strip()


def _allowed_path(abs_path: str, base_root: str) -> bool:
    try:
        ap = os.path.abspath(abs_path)
        base = os.path.abspath(base_root)
        ap_norm, base_norm = os.path.normcase(ap), os.path.normcase(base)
        try:
            return os.path.commonpath([ap_norm, base_norm]) == base_norm
        except Exception:
            return ap_norm.startswith(base_norm)
    except Exception:
        return False


def _check_acl(pn: str, rev: str):
    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, pn, rev):
            return False
    except Exception:
        return True
    return True


@bp.post("/upload/pack")
@csrf.exempt
@login_required
@permissions_required("import.bom")
def upload_pack():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "file required"}), 400
    filename = secure_filename(f.filename)
    dry_run = _parse_bool(request.form.get("dry_run") or request.args.get("dry_run"))
    strict = _parse_bool(request.form.get("strict_structure") or request.args.get("strict_structure"))
    allow_extra = bool(current_app.config.get("EXTRA_FILES_ALLOWED", True))
    try:
        result = import_upload_pack(
            f.read(),
            filename,
            uploaded_by=_uploaded_by(),
            dry_run=dry_run,
            strict_structure=strict,
            allow_extra=allow_extra,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        return jsonify({"error": "upload failed"}), 500
    return jsonify(result)


@bp.get("/parts/<path:pn>/<path:rev>/extra")
@login_required
@require_items_view
def list_extra_files(pn: str, rev: str):
    pn_clean = clean_pn(pn)
    rev_clean = clean_rev(rev_from_token(rev))
    if not pn_clean:
        return jsonify({"error": "pn required"}), 400
    if not _check_acl(pn_clean, rev_clean):
        return jsonify({"error": "forbidden"}), 403

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
        rows.append(
            {
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
                "uploaded_at": ef.uploaded_at.isoformat() if ef.uploaded_at else "",
                "url": extra_file_url_for(ef),
            }
        )
    return jsonify(rows)


@bp.post("/parts/<path:pn>/<path:rev>/extra")
@csrf.exempt
@login_required
@permissions_required("items.edit")
def upload_extra_files(pn: str, rev: str):
    if not current_app.config.get("EXTRA_FILES_ALLOWED", True):
        return jsonify({"error": "extra files disabled"}), 403
    pn_clean = clean_pn(pn)
    rev_clean = clean_rev(rev_from_token(rev))
    if not pn_clean:
        return jsonify({"error": "pn required"}), 400
    if not _check_acl(pn_clean, rev_clean):
        return jsonify({"error": "forbidden"}), 403

    files = request.files.getlist("file")
    if not files:
        files = list(request.files.values())
    if not files:
        return jsonify({"error": "file required"}), 400

    max_file_mb = int(current_app.config.get("UPLOAD_PACK_MAX_FILE_MB") or 0)
    max_bytes = max_file_mb * 1024 * 1024 if max_file_mb else 0
    base_root = extra_root()
    uploaded_by = _uploaded_by()
    created: List[dict] = []
    errors: List[str] = []

    for f in files:
        if not f or not f.filename:
            continue
        filename = os.path.basename(f.filename)
        rel_path = extra_rel_path(pn_clean, rev_clean, filename)
        abs_path = extra_abs_path(rel_path)
        if not base_root or not _allowed_path(abs_path, base_root):
            errors.append(f"blocked path: {filename}")
            continue
        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            f.save(abs_path)
            size = float(os.path.getsize(abs_path))
            if max_bytes and size > max_bytes:
                os.remove(abs_path)
                errors.append(f"file too large: {filename}")
                continue
            mime = guess_mime(abs_path)
            sha = hash_file(abs_path)
            existing = PartExtraFile.objects(
                part_number=pn_clean, revision=rev_clean, rel_path=rel_path
            ).first()
            if existing:
                existing.original_name = filename
                existing.size = size
                existing.mime = mime
                existing.sha256 = sha
                existing.uploaded_by = uploaded_by or existing.uploaded_by
                existing.uploaded_at = datetime.utcnow()
                existing.source = "upload"
                existing.save()
                ef = existing
            else:
                ef = PartExtraFile(
                    part_number=pn_clean,
                    revision=rev_clean,
                    original_name=filename,
                    rel_path=rel_path,
                    size=size,
                    mime=mime,
                    sha256=sha,
                    uploaded_by=uploaded_by,
                    uploaded_at=datetime.utcnow(),
                    source="upload",
                )
                ef.save()
            created.append(
                {
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
                    "uploaded_at": ef.uploaded_at.isoformat() if ef.uploaded_at else "",
                    "url": extra_file_url_for(ef),
                }
            )
        except Exception:
            errors.append(f"failed to save: {filename}")

    return jsonify({"files": created, "errors": errors})


@bp.delete("/parts/<path:pn>/<path:rev>/extra/<file_id>")
@csrf.exempt
@login_required
@permissions_required("items.edit")
def delete_extra_file(pn: str, rev: str, file_id: str):
    pn_clean = clean_pn(pn)
    rev_clean = clean_rev(rev_from_token(rev))
    if not pn_clean:
        return jsonify({"error": "pn required"}), 400
    if not _check_acl(pn_clean, rev_clean):
        return jsonify({"error": "forbidden"}), 403

    ef = PartExtraFile.objects(id=file_id).first()
    if not ef:
        return jsonify({"error": "not found"}), 404
    if (
        (ef.part_number or "").strip().lower() != pn_clean.lower()
        or (ef.revision or "") != rev_clean
    ):
        return jsonify({"error": "not found"}), 404

    base_root = extra_root()
    if ef.rel_path and base_root:
        abs_path = extra_abs_path(ef.rel_path)
        if abs_path and _allowed_path(abs_path, base_root) and os.path.isfile(abs_path):
            try:
                os.remove(abs_path)
            except Exception:
                pass
    ef.delete()
    return jsonify({"ok": True})
