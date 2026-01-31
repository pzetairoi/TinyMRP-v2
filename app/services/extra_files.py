from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from typing import Optional, Tuple

from flask import current_app, url_for
from itsdangerous import BadSignature, URLSafeSerializer

from app.models.extra_file import PartExtraFile


_TOKEN_SALT = "tinymrp.extra.v1"
REV_EMPTY_TOKEN = "__no_rev__"
_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _serializer() -> URLSafeSerializer:
    secret = current_app.config.get("SECRET_KEY") or "change-me"
    return URLSafeSerializer(secret, salt=_TOKEN_SALT)


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
    base = os.path.basename(name or "")
    return safe_segment(base, "file")


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
    payload = {
        "id": str(ef.id),
        "kind": kind or "file",
        "pn": ef.part_number or "",
        "rev": ef.revision or "",
        "rel": ef.rel_path or "",
    }
    return _serializer().dumps(payload)


def resolve_extra_file_token(token: str) -> Optional[Tuple[PartExtraFile, str]]:
    try:
        data = _serializer().loads(token)
    except BadSignature:
        return None
    file_id = data.get("id")
    if not file_id:
        return None
    ef = PartExtraFile.objects(id=file_id).first()
    if not ef:
        return None
    pn = (data.get("pn") or "").strip()
    if pn and ef.part_number and pn != ef.part_number:
        return None
    rev = (data.get("rev") or "").strip()
    if rev and (ef.revision or "") != rev:
        return None
    rel = (data.get("rel") or "").strip()
    if rel and ef.rel_path:
        rel_norm = os.path.normpath(rel).replace("\\", "/").lstrip("/").casefold()
        ef_norm = os.path.normpath(ef.rel_path).replace("\\", "/").lstrip("/").casefold()
        if rel_norm != ef_norm:
            return None
    kind = data.get("kind") or "file"
    return ef, kind


def extra_file_url_for(ef: PartExtraFile, *, kind: str = "file") -> str:
    token = extra_file_token_for(ef, kind=kind)
    return url_for("extra_fileserve.view", token=token)
