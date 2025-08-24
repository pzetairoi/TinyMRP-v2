from flask import Blueprint, request, jsonify, current_app
from app.extensions import csrf
from app.models.artifact import PartFile
from app.services.thumbs import preview_png_urls_for, drawing_png_urls_for
import base64

bp = Blueprint("files_api", __name__, url_prefix="/api")

def _token_url(path: str) -> str:
    tok = base64.urlsafe_b64encode((path or "").encode("utf-8")).decode("ascii")
    return f"/files/view/{tok}"


@bp.get("/part_images")
@csrf.exempt
def part_images():
    pn = (request.args.get("pn") or "").strip()
    mode = (request.args.get("mode") or "preview").strip().lower()
    if not pn:
        return jsonify([])
    # rev optional in your app – if you also pass it, keep using it
    rev = request.args.get("rev")
    if mode == "drawing":
        urls = drawing_png_urls_for(pn, rev)
    else:
        urls = preview_png_urls_for(pn, rev)
    return jsonify([{"urls": urls}])  # keep the shape your ImageStrip expects