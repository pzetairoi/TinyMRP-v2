from flask import Blueprint, jsonify, current_app

bp = Blueprint("processmeta_api", __name__, url_prefix="/api")

@bp.get("/process_meta")
def process_meta():
    meta = dict(current_app.config.get("PROCESS_META") or {})
    meta.pop("_alias_index", None)
    return jsonify(meta)
