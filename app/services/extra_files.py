from __future__ import annotations

import logging

import hashlib
import mimetypes
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Tuple

from flask import current_app, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeSerializer, URLSafeTimedSerializer

from app.models.extra_file import PartExtraFile

logger = logging.getLogger(__name__)


_TOKEN_SALT = "tinymrp.extra.v1"
REV_EMPTY_TOKEN = "__no_rev__"
_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")
_DANGEROUS_EXTENSIONS = frozenset(
    {
        ".app",
        ".bat",
        ".cmd",
        ".com",
        ".cpl",
        ".dll",
        ".exe",
        ".hta",
        ".htm",
        ".html",
        ".jar",
        ".js",
        ".jse",
        ".lnk",
        ".msi",
        ".msp",
        ".php",
        ".ps1",
        ".py",
        ".scr",
        ".sh",
        ".vb",
        ".vbe",
        ".vbs",
        ".wsf",
    }
)


def _secret() -> str:
    return current_app.config.get("SECRET_KEY") or current_app.config.get("SECURITY_PASSWORD_SALT") or ""


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret(), salt=_TOKEN_SALT)


def _legacy_serializer() -> URLSafeSerializer:
    # Pre-TTL tokens (no timestamp). Only honored while FILES_ALLOW_LEGACY_TOKENS is enabled.
    return URLSafeSerializer(_secret(), salt=_TOKEN_SALT)


def rev_to_token(rev: str | None) -> str:
    return rev if (rev or "") else REV_EMPTY_TOKEN


def rev_from_token(token: str | None) -> str:
    if not token:
        return ""
    return "" if token == REV_EMPTY_TOKEN else token


def safe_segment(value: str | None, default: str = "unknown") -> str:
    text = (value or "").strip()
    if not text:
        return default
    text = text.replace("/", "_").replace("\\", "_")
    return _SEGMENT_RE.sub("_", text) or default


def safe_filename(name: str | None) -> str:
    raw = str(name or "")
    base = raw.replace("\\", "/").rsplit("/", 1)[-1]
    value = safe_segment(base, "file").strip(" .")
    if not value or value in {".", ".."}:
        value = "file"
    stem, ext = os.path.splitext(value[:180])
    return f"{stem[:150]}{ext[:20]}" or "file"


def validated_upload_filename(name: str | None) -> str:
    raw = str(name or "")
    if not raw or "\x00" in raw or any(ord(char) < 32 for char in raw):
        raise ValueError("invalid file")
    filename = safe_filename(raw)
    if Path(filename).suffix.casefold() in _DANGEROUS_EXTENSIONS:
        raise ValueError("unsupported file type")
    if filename.casefold() in {
        "con",
        "prn",
        "aux",
        "nul",
        "com1",
        "lpt1",
    }:
        raise ValueError("invalid file")
    return filename


def extra_root() -> str:
    root = current_app.config.get("EXTRA_FILES_ROOT")
    if root:
        return str(root).strip().rstrip("/\\")
    base = (
        current_app.config.get("FILES_LOCAL_ROOT")
        or current_app.config.get("FILE_ROOT_LOCAL")
        or ""
    ).strip()
    if not base:
        return ""
    return base


def extra_rel_path(pn: str, rev: str, filename: str, subpath: str = "") -> str:
    pn_seg = safe_segment(pn)
    rev_seg = safe_segment(rev_to_token(rev))
    parts = ["extra", pn_seg, rev_seg]
    if subpath:
        for piece in subpath.replace("\\", "/").split("/"):
            if piece:
                parts.append(safe_segment(piece))
    parts.append(safe_filename(filename))
    return "/".join(parts)


def extra_abs_path(rel_path: str) -> str:
    root = extra_root()
    rel_norm = rel_path.replace("\\", "/").lstrip("/")
    rel_norm = os.path.normpath(rel_norm).replace("\\", "/")
    return os.path.abspath(os.path.join(root, rel_norm))


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def guess_mime(path: str, fallback: str = "application/octet-stream") -> str:
    mt, _ = mimetypes.guess_type(path)
    return mt or fallback


def extra_file_token_for(ef: PartExtraFile, kind: str = "file") -> str:
    identity = PartExtraFile.objects(id=getattr(ef, "id", None)).only(
        "part_number",
        "revision",
        "rel_path",
    ).first()
    if identity is None:
        raise ValueError("file unavailable")
    payload = {
        "id": str(identity.id),
        "kind": kind or "file",
        "pn": identity.part_number or "",
        "rev": identity.revision or "",
        "rel": identity.rel_path or "",
    }
    return _serializer().dumps(payload)


def resolve_extra_file_token(token: str) -> Optional[Tuple[PartExtraFile, str]]:
    from app.services.files_access import token_ttl_seconds

    ttl = token_ttl_seconds()
    data = None
    try:
        if ttl > 0:
            data = _serializer().loads(token, max_age=ttl)
        else:
            data = _serializer().loads(token)
    except SignatureExpired:
        return None
    except BadSignature:
        if bool(current_app.config.get("FILES_ALLOW_LEGACY_TOKENS")):
            try:
                data = _legacy_serializer().loads(token)
            except BadSignature:
                return None
        else:
            return None
    if not isinstance(data, dict):
        return None
    file_id = data.get("id")
    if not file_id:
        return None
    ef = PartExtraFile.objects(id=file_id).first()
    if not ef:
        return None
    if "pn" not in data or "rev" not in data or "rel" not in data:
        return None
    pn = str(data.get("pn") or "").strip()
    if pn != str(ef.part_number or "").strip():
        return None
    rev = str(data.get("rev") or "").strip()
    if rev != str(ef.revision or "").strip():
        return None
    rel = (data.get("rel") or "").strip()
    if rel and ef.rel_path:
        rel_norm = os.path.normpath(rel).replace("\\", "/").lstrip("/").casefold()
        ef_norm = os.path.normpath(ef.rel_path).replace("\\", "/").lstrip("/").casefold()
        if rel_norm != ef_norm:
            return None
    kind = str(data.get("kind") or "file")
    if kind != "file":
        return None
    return ef, kind


def extra_file_url_for(ef: PartExtraFile, *, kind: str = "file") -> str:
    token = extra_file_token_for(ef, kind=kind)
    return url_for("extra_fileserve.view", token=token)


def store_associated_uploads(
    uploads,
    *,
    part_number: str,
    revision: str,
    uploaded_by: str,
    max_bytes: int = 0,
) -> list[PartExtraFile]:
    """Validate, stage, and atomically install one associated-file batch."""

    from app.services.file_security import (
        FileSecurityError,
        associated_storage_root,
        resolve_associated_path,
    )
    from app.services.timezone_utils import utc_now

    prepared: list[dict] = []
    names: set[str] = set()
    root = associated_storage_root()
    root.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix=".tinymrp-stage-", dir=str(root)))
    try:
        for upload in uploads:
            filename = validated_upload_filename(getattr(upload, "filename", ""))
            name_key = filename.casefold()
            if name_key in names:
                raise ValueError("duplicate file")
            names.add(name_key)
            rel_path = extra_rel_path(part_number, revision, filename)
            existing = PartExtraFile.objects(
                part_number__iexact=part_number,
                revision__iexact=revision,
                rel_path=rel_path,
            ).first()
            probe = existing or PartExtraFile(
                part_number=part_number,
                revision=revision,
                original_name=filename,
                rel_path=rel_path,
            )
            try:
                final_path = resolve_associated_path(probe, must_exist=False)
            except FileSecurityError as exc:
                raise ValueError("invalid file") from exc
            if final_path.exists() and existing is None:
                raise ValueError("file conflict")

            staged_path = stage_dir / f"{uuid.uuid4().hex}{Path(filename).suffix}"
            upload.save(str(staged_path))
            if not staged_path.is_file():
                raise ValueError("invalid file")
            size = staged_path.stat().st_size
            if max_bytes and size > max_bytes:
                raise ValueError("file too large")
            prepared.append(
                {
                    "filename": filename,
                    "rel_path": rel_path,
                    "existing": existing,
                    "final_path": final_path,
                    "staged_path": staged_path,
                    "size": float(size),
                    "mime": guess_mime(str(staged_path)),
                    "sha256": hash_file(str(staged_path)),
                }
            )

        completed: list[dict] = []
        records: list[PartExtraFile] = []
        try:
            for item in prepared:
                final_path: Path = item["final_path"]
                final_path.parent.mkdir(parents=True, exist_ok=True)
                backup = stage_dir / f"{uuid.uuid4().hex}.backup"
                had_backup = final_path.exists()
                if had_backup:
                    os.replace(final_path, backup)
                try:
                    os.replace(item["staged_path"], final_path)
                    existing = item["existing"]
                    if existing is None:
                        record = PartExtraFile(
                            part_number=part_number,
                            revision=revision,
                            original_name=item["filename"],
                            rel_path=item["rel_path"],
                            size=item["size"],
                            mime=item["mime"],
                            sha256=item["sha256"],
                            uploaded_by=uploaded_by,
                            uploaded_at=utc_now(),
                            source="upload",
                        )
                        snapshot = None
                    else:
                        record = existing
                        snapshot = {
                            "original_name": record.original_name,
                            "size": record.size,
                            "mime": record.mime,
                            "sha256": record.sha256,
                            "uploaded_by": record.uploaded_by,
                            "uploaded_at": record.uploaded_at,
                            "source": record.source,
                        }
                        record.original_name = item["filename"]
                        record.size = item["size"]
                        record.mime = item["mime"]
                        record.sha256 = item["sha256"]
                        record.uploaded_by = uploaded_by or record.uploaded_by
                        record.uploaded_at = utc_now()
                        record.source = "upload"
                    record.save()
                    completed.append(
                        {
                            "record": record,
                            "snapshot": snapshot,
                            "final_path": final_path,
                            "backup": backup if had_backup else None,
                        }
                    )
                    records.append(record)
                except Exception:
                    if final_path.exists():
                        final_path.unlink()
                    if had_backup and backup.exists():
                        os.replace(backup, final_path)
                    raise
        except Exception:
            for item in reversed(completed):
                record = item["record"]
                snapshot = item["snapshot"]
                try:
                    if snapshot is None:
                        record.delete()
                    else:
                        for field, value in snapshot.items():
                            setattr(record, field, value)
                        record.save()
                except Exception:
                    # This IS the rollback. Failing here leaves the database
                    # holding a record the filesystem no longer matches, and
                    # silence made that unrecoverable - nothing said which
                    # record to reconcile.
                    logger.exception(
                        "rollback failed for associated upload record %s",
                        getattr(record, "id", "?"),
                    )
                final_path = item["final_path"]
                backup = item["backup"]
                try:
                    if final_path.exists():
                        final_path.unlink()
                    if backup is not None and backup.exists():
                        os.replace(backup, final_path)
                except OSError:
                    pass
            raise

        for item in completed:
            backup = item["backup"]
            if backup is not None and backup.exists():
                backup.unlink()
        return records
    finally:
        for item in prepared:
            staged_path = item.get("staged_path")
            if staged_path and Path(staged_path).exists():
                Path(staged_path).unlink()
        try:
            for child in stage_dir.iterdir():
                if child.is_file():
                    child.unlink()
            stage_dir.rmdir()
        except OSError:
            pass


def purge_associated_file(file_record: PartExtraFile) -> bool:
    """Quarantine the physical file, remove metadata, then finalise deletion."""

    from app.services.file_security import (
        associated_storage_root,
        resolve_associated_path,
    )

    path = resolve_associated_path(file_record, must_exist=False)
    root = associated_storage_root()
    root.mkdir(parents=True, exist_ok=True)
    quarantine_dir = Path(
        tempfile.mkdtemp(prefix=".tinymrp-quarantine-", dir=str(root))
    )
    quarantine = quarantine_dir / uuid.uuid4().hex
    moved = False
    try:
        if path.exists():
            if not path.is_file():
                raise ValueError("file unavailable")
            os.replace(path, quarantine)
            moved = True
        try:
            file_record.delete()
        except Exception:
            if moved and quarantine.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(quarantine, path)
            raise
        if moved and quarantine.exists():
            quarantine.unlink()
        return True
    finally:
        try:
            if quarantine.exists():
                quarantine.unlink()
            quarantine_dir.rmdir()
        except OSError:
            pass
