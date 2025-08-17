from flask import Blueprint, request, jsonify, current_app
from app.extensions import csrf
from app.models.artifact import PartFile
import base64

bp = Blueprint("files_api", __name__, url_prefix="/api")

def _token_url(path: str) -> str:
    tok = base64.urlsafe_b64encode((path or "").encode("utf-8")).decode("ascii")
    return f"/files/view/{tok}"


@bp.get("/part_images")
@csrf.exempt
def part_images():
    pn  = (request.args.get("pn") or "").strip()
    rev = request.args.get("rev")  # keep None vs "" distinction
    if pn == "":
        return jsonify([])

    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")

    def build_rows(q):
        rows = []
        for f in PartFile.objects(**q).order_by("-mtime", "path"):
            urls = []
            if http_base and f.rel_path:
                urls.append(f"{http_base}/{f.rel_path}")
            # token fallback
            tok = base64.urlsafe_b64encode((f.path or "").encode("utf-8")).decode("ascii")
            urls.append(f"/files/view/{tok}")
            rows.append({
                "urls": urls,
                "best": urls[0],
                "revision": f.revision or "",
                "ext": f.ext, "group": f.ext_group,
                "mtime": f.mtime.isoformat() if f.mtime else None,
            })
        return rows

    # Case A: client sent ?rev= (present but empty) -> return ONLY empty-rev files
    if rev is not None and (rev or "").strip() == "":
        rows = build_rows({"part_number": pn, "revision": "", "ext_group__in": ["png"]})
        return jsonify(rows)

    # Case B: client sent a concrete rev -> filter by that
    if rev:
        rows = build_rows({"part_number": pn, "revision": rev.strip(), "ext_group__in": ["png"]})
        return jsonify(rows)

    # Case C: no rev param -> prefer empty-rev if any, else latest rev group
    all_docs = list(PartFile.objects(part_number=pn, ext_group__in=["png"]).order_by("-mtime", "path"))
    if not all_docs:
        return jsonify([])

    empties = [d for d in all_docs if (d.revision or "") == ""]
    if empties:
        return jsonify(build_rows({"part_number": pn, "revision": "", "ext_group__in": ["png"]}))

    # latest group by revision
    latest_rev = (all_docs[0].revision or "")
    # If latest is empty, the above empties branch would have taken it, so latest here is non-empty
    return jsonify(build_rows({"part_number": pn, "revision": latest_rev, "ext_group__in": ["png"]}))
