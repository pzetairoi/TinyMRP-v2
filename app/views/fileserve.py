import os, mimetypes
from urllib.parse import unquote
from flask import Blueprint, current_app, send_file, abort, request, g
from flask_login import login_required, current_user
from app.services.audit import log_action
from app.services.acl import allowed_parts_for, part_is_allowed
from app.services.files_access import resolve_file_token
from app.services.app_settings import resolve_file_sources
from app.models.artifact import PartFile

bp = Blueprint("fileserve", __name__, url_prefix="/files")

def _configured_roots() -> list[str]:
    roots: list[str] = []
    try:
        configured = current_app.config.get("FILE_SOURCES")
        if isinstance(configured, list) and configured:
            sources = [dict(item) for item in configured if isinstance(item, dict)]
        else:
            sources = resolve_file_sources()
        for source in sources:
            root = str(source.get("local_root") or "").strip()
            if root:
                roots.append(os.path.abspath(root))
    except Exception:
        pass
    fallback = (current_app.config.get("FILE_ROOT_LOCAL") or "").strip()
    if fallback:
        fallback_abs = os.path.abspath(fallback)
        if fallback_abs not in roots:
            roots.append(fallback_abs)
    return roots

def _allowed_path(abs_path: str) -> bool:
    try:
        ap = os.path.abspath(abs_path)
        for base in _configured_roots():
            if not base:
                continue
            ap_norm, base_norm = os.path.normcase(ap), os.path.normcase(base)
            try:
                if os.path.commonpath([ap_norm, base_norm]) == base_norm:
                    return True
            except Exception:
                if ap_norm.startswith(base_norm):
                    return True
        return False
    except Exception:
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
    if kind == "thumb" and getattr(pf, "thumb_rel_path", None):
        rel_norm = _safe_rel_path(pf.thumb_rel_path)
        if rel_norm:
            abs_path = _abs_from_rel(rel_norm)
            if abs_path and os.path.isfile(abs_path):
                return abs_path, rel_norm
    if getattr(pf, "path", None) and os.path.isabs(pf.path):
        rel = _rel_from_abs(pf.path) or getattr(pf, "rel_path", None)
        return pf.path, rel
    rel = None
    if getattr(pf, "rel_path", None):
        rel = pf.rel_path
    if rel:
        rel_norm = _safe_rel_path(rel)
        if rel_norm:
            abs_path = _abs_from_rel(rel_norm)
            return abs_path, rel_norm
    if getattr(pf, "path", None):
        pth = pf.path
        abs_path = pth if os.path.isabs(pth) else _abs_from_rel(pth)
        return abs_path, _rel_from_abs(abs_path or "")
    return None, None


@bp.get("/view/<token>")
@login_required
def view(token: str):
    resolved = resolve_file_token(token)
    if not resolved and current_app.config.get("FILES_ALLOW_LEGACY_TOKENS"):
        try:
            import base64
            legacy_path = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        except Exception:
            legacy_path = ""
        if legacy_path and _allowed_path(legacy_path) and os.path.isfile(legacy_path):
            rel = _rel_from_abs(legacy_path)
            try:
                from mongoengine.queryset.visitor import Q
                rel_norm = rel or ""
                pf = PartFile.objects(Q(rel_path=rel_norm) | Q(rel_path__iexact=rel_norm)).first()
            except Exception:
                pf = None
            if pf:
                resolved = (pf, "file")
    if not resolved:
        abort(404)
    pf, kind = resolved
    if kind == "preview":
        g.allow_frame_embedding = True
    # ACL: enforce PN/REV access
    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, pf.part_number, pf.revision or ""):
            return abort(403)
    except Exception:
        pass
    path, rel = _path_for_pf(pf, kind)
    if not path or not os.path.isfile(path) or not _allowed_path(path):
        if rel and (current_app.config.get("FILES_UPSTREAM_BASE") or "").strip():
            try:
                from app.files_proxy import _proxy
                return _proxy(rel, rel_path=rel)
            except Exception:
                pass
        abort(404)
    ct, _ = mimetypes.guess_type(path)
    try:
        log_action("file.view", resource_type="file", resource=(rel or pf.rel_path or "unknown"))
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
        pf = PartFile.objects(Q(rel_path=rel_norm) | Q(rel_path__iexact=rel_norm)).first()
        if not pf:
            return ("", 404)
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, pf.part_number, pf.revision or ""):
            return ("", 403)
    except Exception:
        return ("", 403)
    return ("", 204)
