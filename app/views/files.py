# app/views/files.py
from flask import Blueprint, request, jsonify, current_app, url_for
import os, base64
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
def part_images():
    pn   = (request.args.get("pn") or "").strip()
    mode = (request.args.get("mode") or "preview").strip().lower()  # preview|drawing|all
    rev  = request.args.get("rev")  # keep None vs "" distinction

    if not pn:
        return jsonify([])

    rev = _rev_for(pn, rev)

    qs = PartFile.objects(part_number__iexact=pn, revision__iexact=rev, ext_group="png")
    for d in qs:
        print("dpartnumber",d.part_number)
        print("rev ",d.revision)
        print("ext group ",d.ext_group)
        print("is dwg",d.is_dwg)
    if mode == "preview":
        qs = qs.filter(is_dwg=False)
    elif mode == "drawing":
        qs = qs.filter(is_dwg=True)
    else:
        # "all" -> both
        pass

    local_root = (current_app.config.get("FILE_ROOT_LOCAL") or "").rstrip("/\\")
    http_base = (current_app.config.get("FILE_ROOT_HTTP") or current_app.config.get("FILES_URL_PREFIX") or "").rstrip("/")
    rows = []
    for d in qs.order_by("-mtime_iso"):
        urls: list[str] = []
        # 1) Prefer direct HTTP url if saved by the scanner
        if getattr(d, "http_url", None):
            urls.append(d.http_url)

        # 2) Build HTTP URL from configured prefix if rel_path exists
        if getattr(d, "rel_path", None) and http_base:
            urls.append(f"{http_base}/{d.rel_path}")

        # 3) Fallback to fileserve token using rel_path
        if getattr(d, "rel_path", None) and local_root:
            abs_path = os.path.normpath(os.path.join(local_root, d.rel_path.replace("/", os.sep)))
            # Use URL-safe base64 to be safe in URLs
            token = base64.urlsafe_b64encode(abs_path.encode("utf-8")).decode("ascii")
            urls.append(url_for("fileserve.view", token=token))

        # de-duplicate while preserving order
        seen = set()
        dedup = []
        for u in urls:
            if u and u not in seen:
                seen.add(u)
                dedup.append(u)

        rows.append({"urls": dedup, "revision": d.revision})
    return jsonify(rows)
