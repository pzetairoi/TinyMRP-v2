# app/views/importer.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from app.extensions import csrf
from app.services.import_zip import import_bom_zip

bp = Blueprint("importer", __name__, url_prefix="/import")

@bp.get("/")
def upload_form():
    # Simple Jinja page with a file input - extends base so navbar shows.
    return render_template("import/upload.html")

@bp.post("/")
@csrf.exempt  # keep it simple; remove if you wire a WTForm with CSRF token
def upload_post():
    f = request.files.get("file")
    if not f or not f.filename:
        flash("Please choose a .zip file.", "warning")
        return redirect(url_for("importer.upload_form"))
    fn = secure_filename(f.filename)
    result = import_bom_zip(f.read(), fn, seed_tag="upload")
    thumbs = result.get('thumbnails_generated') or result.get('thumbnails_built') or 0
    flash(
        f"Imported {result['zip']} - root={result['root']} - parts+{result['parts_created']} links+{result['links_created']} - thumbs={thumbs}",
        "success",
    )
    return render_template("import/result.html", result=result)

# Optional: JSON API endpoint for programmatic uploads
@bp.post("/api")
@csrf.exempt
def upload_api():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "file required"}), 400
    fn = secure_filename(f.filename)
    result = import_bom_zip(f.read(), fn, seed_tag="upload-api")
    return jsonify(result)
