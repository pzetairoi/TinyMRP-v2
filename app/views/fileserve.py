import os, mimetypes
from pathlib import Path
from urllib.parse import unquote
from flask import Blueprint, current_app, send_file, abort, request, g
from flask_login import login_required, current_user
from app.services.audit import log_action
from app.services.files_access import resolve_file_token
from app.services.file_security import (
    FileSecurityError,
    managed_file_read_allowed,
    managed_storage_roots,
    resolve_managed_path,
)
from app.models.artifact import PartFile

bp = Blueprint("fileserve", __name__, url_prefix="/files")

def _configured_roots() -> list[str]:
    try:
        return [str(root.path) for root in managed_storage_roots()]
    except Exception:
        return []

def _allowed_path(abs_path: str) -> bool:
    try:
        resolved = Path(abs_path).resolve(strict=True)
        if not resolved.is_file():
            return False
        for root in managed_storage_roots():
            try:
                resolved.relative_to(root.path)
            except (ValueError, OSError):
                continue
            else:
                return True
        return False
    except (OSError, RuntimeError, ValueError):
        return False

def _safe_rel_path(rel: str) -> str | None:
    if not rel:
        return None
    rel_norm = rel.replace("\\", "/").lstrip("/")
    rel_norm = os.path.normpath(rel_norm).replace("\\", "/")
    if rel_norm in (".", ""):
        return None
    if rel_norm.startswith(".."):
        return None
    return rel_norm


def _root_local() -> str:
    return (current_app.config.get("FILE_ROOT_LOCAL") or "").strip()


def _abs_from_rel(rel: str) -> str | None:
    base = _root_local()
    if not base:
        return None
    rel_norm = _safe_rel_path(rel)
    if not rel_norm:
        return None
    return os.path.abspath(os.path.join(base, rel_norm))


def _rel_from_abs(abs_path: str) -> str | None:
    base = _root_local()
    if not base:
        return None
    ap = os.path.abspath(abs_path)
    base = os.path.abspath(base)
    try:
        rel = os.path.relpath(ap, base)
    except Exception:
        return None
    return _safe_rel_path(rel)


def _path_for_pf(pf: PartFile, kind: str) -> tuple[str | None, str | None]:
    try:
        path = resolve_managed_path(
            pf,
            kind="thumb" if kind == "thumb" else "file",
            must_exist=True,
        )
    except FileSecurityError:
        return None, None
    rel = pf.thumb_rel_path if kind == "thumb" else pf.rel_path
    return str(path), _safe_rel_path(rel or "")


@bp.get("/view/<token>")
@login_required
def view(token: str):
    resolved = resolve_file_token(token)
    if not resolved:
        abort(404)
    pf, kind = resolved
    if kind == "preview":
        g.allow_frame_embedding = True
    if not managed_file_read_allowed(current_user, pf):
        abort(404)
    path, rel = _path_for_pf(pf, kind)
    if not path:
        try:
            candidate = resolve_managed_path(
                pf,
                kind="thumb" if kind == "thumb" else "file",
                must_exist=False,
            )
            rel = _safe_rel_path(
                pf.thumb_rel_path if kind == "thumb" else pf.rel_path
            )
        except FileSecurityError:
            candidate = None
        if candidate is not None and rel and (
            current_app.config.get("FILES_UPSTREAM_BASE") or ""
        ).strip():
            try:
                from app.files_proxy import _proxy
                return _proxy(rel, rel_path=rel)
            except Exception:
                pass
        abort(404)
    ct, _ = mimetypes.guess_type(path)
    try:
        log_action(
            "file.view",
            resource_type="file",
            resource=f"partfile:{pf.id}",
            meta={"part": f"{pf.part_number}:{pf.revision or ''}", "kind": kind},
        )
    except Exception:
        pass

    accel_prefix = (current_app.config.get("FILES_ACCEL_REDIRECT_PREFIX") or "").rstrip("/")
    if accel_prefix and rel:
        resp = current_app.response_class("")
        resp.headers["X-Accel-Redirect"] = f"{accel_prefix}/{rel}"
        resp.headers["Content-Type"] = ct or "application/octet-stream"
        resp.headers["Cache-Control"] = "private, max-age=3600"
        return resp

    resp = send_file(path, mimetype=ct or "application/octet-stream",
                     conditional=True, max_age=3600)
    resp.headers["Cache-Control"] = "private, max-age=3600"
    return resp


@bp.get("/auth")
def auth():
    if not getattr(current_user, "is_authenticated", False):
        return ("", 401)
    uri = (
        request.headers.get("X-Original-URI")
        or request.headers.get("X-Original-URL")
        or request.args.get("path")
        or ""
    )
    if not uri:
        return ("", 400)
    path = uri.split("?", 1)[0]
    path = unquote(path)
    prefixes = []
    for cand in (current_app.config.get("FILES_URL_PREFIX") or "", "/deliverables", "/Deliverables"):
        cand = cand.strip()
        if cand:
            prefixes.append(cand.rstrip("/"))
    rel = None
    for pref in prefixes:
        if path.startswith(pref + "/"):
            rel = path[len(pref) + 1:]
            break
    if not rel:
        return ("", 403)
    rel_norm = _safe_rel_path(rel)
    if not rel_norm:
        return ("", 403)
    try:
        from mongoengine.queryset.visitor import Q

        matches = [
            pf
            for pf in PartFile.objects(
                Q(rel_path=rel_norm) | Q(rel_path__iexact=rel_norm)
            )
            if managed_file_read_allowed(current_user, pf)
        ]
        if len(matches) != 1:
            return ("", 404)
        resolve_managed_path(matches[0], must_exist=False)
    except Exception:
        return ("", 403)
    return ("", 204)
