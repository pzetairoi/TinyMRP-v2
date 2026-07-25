# app/views/files.py
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.authorization import require_permission
from app.services.audit import log_action
from app.services.file_security import (
    exact_file_part,
    managed_file_category_allowed,
    managed_file_path_allowed,
    managed_thumbnail_available,
)
from app.services.files_access import file_url_for
from app.services.part_drawing_markups import source_fingerprint_for
from app.services.timezone_utils import utc_iso
from app.models.artifact import PartFile

bp = Blueprint("files_api", __name__, url_prefix="/api")

@bp.get("/part_images")
@login_required
@require_permission("files.read")
def part_images():
    pn   = (request.args.get("pn") or "").strip()
    mode = (request.args.get("mode") or "preview").strip().lower()  # preview|drawing|all
    rev  = request.args.get("rev")  # keep None vs "" distinction

    if not pn:
        return jsonify([])

    rev = rev if rev is not None else ""
    if exact_file_part(current_user, pn, rev) is None:
        return jsonify([]), 404

    qs = PartFile.objects(part_number__iexact=pn, revision__iexact=rev, ext_group="png")
    if mode == "preview":
        qs = qs.filter(is_dwg=False)
    elif mode == "drawing":
        qs = qs.filter(is_dwg=True)
    else:
        # "all" -> both
        pass

    rows = []
    for d in qs.order_by("-mtime_iso"):
        if (
            not managed_file_category_allowed(current_user, d)
            or not managed_file_path_allowed(d)
        ):
            continue
        urls: list[str] = []
        prefer_thumb = not bool(getattr(d, "is_dwg", False))

        try:
            if prefer_thumb and managed_thumbnail_available(d):
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
