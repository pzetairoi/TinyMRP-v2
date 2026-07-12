# app/views/files.py
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.services.acl import require_items_view, allowed_parts_for, part_is_allowed
from app.services.audit import log_action
from app.services.files_access import file_url_for, public_file_urls_enabled
from app.services.part_drawing_markups import source_fingerprint_for
from app.services.timezone_utils import utc_iso
from app.models.part import Part
from app.models.artifact import PartFile

bp = Blueprint("files_api", __name__, url_prefix="/api")

def _rev_for(pn: str, qs_rev: str | None) -> str:
    """
    If caller passed rev (including empty ""), use it as-is.
    Else try the Part.revision; if none, default "".
    """
    if qs_rev is not None:
        return qs_rev
    p = Part.objects(part_number=pn).only("revision").first()
    return (p.revision or "") if p else ""

@bp.get("/part_images")
@login_required
@require_items_view
def part_images():
    pn   = (request.args.get("pn") or "").strip()
    mode = (request.args.get("mode") or "preview").strip().lower()  # preview|drawing|all
    rev  = request.args.get("rev")  # keep None vs "" distinction

    if not pn:
        return jsonify([])

    rev = _rev_for(pn, rev)

    # ACL: enforce root access for PN/REV
    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, pn, rev or ""):
            return jsonify([]), 403
    except Exception:
        pass

    qs = PartFile.objects(part_number__iexact=pn, revision__iexact=rev, ext_group="png")
    if mode == "preview":
        qs = qs.filter(is_dwg=False)
    elif mode == "drawing":
        qs = qs.filter(is_dwg=True)
    else:
        # "all" -> both
        pass

    http_base = (current_app.config.get("FILE_ROOT_HTTP") or current_app.config.get("FILES_URL_PREFIX") or "").rstrip("/")
    allow_public = public_file_urls_enabled()
    rows = []
    for d in qs.order_by("-mtime_iso"):
        urls: list[str] = []
        prefer_thumb = not bool(getattr(d, "is_dwg", False))

        # 1) Public thumbnail URLs only if explicitly allowed (preview images only)
        if prefer_thumb and allow_public and http_base and getattr(d, "thumb_rel_path", None):
            urls.append(f"{http_base}/{d.thumb_rel_path}")

        # 2) Public URLs only if explicitly allowed
        if allow_public and getattr(d, "http_url", None):
            urls.append(d.http_url)

        # 3) Public prefix if explicitly allowed
        if allow_public and getattr(d, "rel_path", None) and http_base:
            urls.append(f"{http_base}/{d.rel_path}")

        # 4) Secure tokenized URL
        try:
            if prefer_thumb and getattr(d, "thumb_rel_path", None):
                urls.append(file_url_for(d, kind="thumb"))
            urls.append(file_url_for(d))
        except Exception:
            pass

        # de-duplicate while preserving order
        seen = set()
        dedup = []
        for u in urls:
            if u and u not in seen:
                seen.add(u)
                dedup.append(u)

        # Full-size image URLs (no thumbnails) for the markup editor: parts
        # without an exported drawing can be marked up on their preview PNG.
        full_urls: list[str] = []
        if allow_public and getattr(d, "http_url", None):
            full_urls.append(d.http_url)
        if allow_public and getattr(d, "rel_path", None) and http_base:
            full_urls.append(f"{http_base}/{d.rel_path}")
        try:
            full_urls.append(file_url_for(d))
        except Exception:
            pass
        seen_full = set()
        dedup_full = []
        for u in full_urls:
            if u and u not in seen_full:
                seen_full.add(u)
                dedup_full.append(u)

        # Every PNG row carries safe source metadata so the markup editor can
        # identify the exact source file. No filesystem paths, no tokens.
        mtime = getattr(d, "mtime_iso", None) or getattr(d, "mtime", None)
        row = {
            "urls": dedup,
            "revision": d.revision,
            "id": str(d.id),
            "source_file_id": str(d.id),
            "is_dwg": bool(getattr(d, "is_dwg", False)),
            "rel_path": d.rel_path or "",
            "sha256": getattr(d, "sha256", "") or "",
            "size": d.size,
            "mtime": utc_iso(mtime),
            "source_fingerprint": source_fingerprint_for(d),
            "image_urls": dedup_full,
        }
        rows.append(row)
    try:
        log_action("file.list", resource_type="file", resource=f"{pn}:{rev}")
    except Exception:
        pass
    return jsonify(rows)
