import logging
import os, mimetypes
from urllib.parse import unquote
from flask import Blueprint, current_app, send_file, abort, request, g
from flask_login import login_required, current_user
from app.services.files_access import resolve_file_token
from app.services.file_security import (
    FileSecurityError,
    managed_file_read_allowed,
    managed_storage_roots,
    readable_managed_file_for_rel_path,
    resolve_managed_path,
)
from app.models.artifact import PartFile

logger = logging.getLogger(__name__)

bp = Blueprint("fileserve", __name__, url_prefix="/files")

def _configured_roots() -> list[str]:
    try:
        return [str(root.path) for root in managed_storage_roots()]
    except Exception:
        # No roots means nothing is servable, so EVERY file 404s. That is the
        # safe direction and the most misleading one: it looks exactly like an
        # instance whose files were never imported.
        logger.exception("could not resolve managed storage roots; serving no files")
        return []

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
    """Authorisation subrequest for a reverse proxy serving deliverables.

    nginx's auth_request understands exactly three answers: 2xx allows the
    request, 401 and 403 deny it, and ANY other status is "auth request
    unexpected status" - which nginx turns into a 500 for the end user. So
    every refusal here must be 401 or 403, never 400 or 404, however tempting
    a more precise code looks.

    403 covers both "no such file" and "not allowed to read it", which is also
    the non-disclosing answer: the two cases must not be distinguishable.
    """
    if not getattr(current_user, "is_authenticated", False):
        return ("", 401)
    uri = (
        request.headers.get("X-Original-URI")
        or request.headers.get("X-Original-URL")
        or request.args.get("path")
        or ""
    )
    if not uri:
        return ("", 403)
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
        record = readable_managed_file_for_rel_path(current_user, rel_norm)
        if record is None:
            # Not 404: nginx cannot interpret it and answers the user with a
            # 500 instead of denying the download.
            return ("", 403)
        resolve_managed_path(record, must_exist=False)
    except Exception:
        # Refusing is correct - this is the path-traversal guard - but a 403
        # caused by a resolver bug and a 403 caused by an actual traversal
        # attempt should not be indistinguishable in the logs.
        logger.exception("managed path resolution failed; refusing the request")
        return ("", 403)
    return ("", 204)
