from __future__ import annotations

from typing import Optional, Tuple
import os

from flask import current_app, url_for
from itsdangerous import BadSignature, URLSafeSerializer

from app.models.artifact import PartFile


_TOKEN_SALT = "tinymrp.files.v1"


def _serializer() -> URLSafeSerializer:
    secret = current_app.config.get("SECRET_KEY") or "change-me"
    return URLSafeSerializer(secret, salt=_TOKEN_SALT)


def public_file_urls_enabled() -> bool:
    val = current_app.config.get("FILES_PUBLIC_URLS")
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def file_token_for(pf: PartFile, kind: str = "file") -> str:
    payload = {
        "id": str(pf.id),
        "kind": kind or "file",
        "pn": pf.part_number or "",
        "rev": pf.revision or "",
    }
    if pf.rel_path:
        payload["rel"] = pf.rel_path
    return _serializer().dumps(payload)


def resolve_file_token(token: str) -> Optional[Tuple[PartFile, str]]:
    try:
        data = _serializer().loads(token)
    except BadSignature:
        return None
    file_id = data.get("id")
    if not file_id:
        return None
    pf = PartFile.objects(id=file_id).first()
    if not pf:
        return None
    pn = (data.get("pn") or "").strip()
    if pn and pf.part_number and pn != pf.part_number:
        return None
    rev = (data.get("rev") or "").strip()
    if rev and (pf.revision or "") != rev:
        return None
    rel = (data.get("rel") or "").strip()
    if rel and pf.rel_path:
        rel_norm = os.path.normpath(rel).replace("\\", "/").lstrip("/").casefold()
        pf_norm = os.path.normpath(pf.rel_path).replace("\\", "/").lstrip("/").casefold()
        if rel_norm != pf_norm:
            return None
    kind = data.get("kind") or "file"
    return pf, kind


def file_url_for(pf: PartFile, *, kind: str = "file") -> str:
    token = file_token_for(pf, kind=kind)
    return url_for("fileserve.view", token=token)
