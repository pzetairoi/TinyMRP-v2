# app/views/admin.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask import abort
from mongoengine.errors import DoesNotExist, ValidationError
from flask_security import roles_required, current_user
from flask_security.utils import hash_password
from app.services.audit import log_action
from app.services.authorization import require_permission
from ..models.auth import User, Role
from ..models.job import Job
from ..models.supplier import Supplier
from ..models.customer import Customer
from ..models.api_token import ApiToken
from ..models.user_settings import UserSettings
from app.services.app_settings import branding_root, get_app_settings
from app.services.password_policy import validate_admin_password
from app.services.processmeta import load_process_meta, sanitize_process_meta
from app.services.timezone_utils import (
    clear_timezone_cache,
    format_display_ts,
    resolve_timezone_name,
    timezone_choices,
    utc_now,
)
from werkzeug.utils import secure_filename
import os
import re


def _safe_process_svg(raw: bytes) -> bool:
    try:
        from defusedxml import ElementTree as SafeET

        root = SafeET.fromstring(raw)
    except Exception:
        return False
    for element in root.iter():
        tag = str(element.tag or "").rsplit("}", 1)[-1].lower()
        if tag in ("script", "foreignobject", "iframe", "object", "embed"):
            return False
        for raw_name, raw_value in element.attrib.items():
            name = str(raw_name or "").rsplit("}", 1)[-1].lower()
            value = str(raw_value or "").strip().lower()
            if name.startswith("on"):
                return False
            if name in ("href", "src") and value.startswith(("javascript:", "data:", "http:", "https:", "//")):
                return False
    return str(root.tag or "").rsplit("}", 1)[-1].lower() == "svg"


def _parse_hw_folders(value: str) -> list[str]:
    raw = [p.strip() for p in re.split(r"[,;\r\n]+", value or "") if p.strip()]
    seen = set()
    out: list[str] = []
    for item in raw:
        token = item.strip().lower()
        if not token or token in seen:
            continue
        out.append(token)
        seen.add(token)
    return out


def _parse_flat_pattern_names(value: str) -> list[str]:
    raw = [p.strip() for p in re.split(r"[,;\r\n]+", value or "") if p.strip()]
    seen = set()
    out: list[str] = []
    for item in raw:
        token = item.strip().lower()
        if not token or token in seen:
            continue
        out.append(token)
        seen.add(token)
    return out


def _parse_int(value: str, default_value: int) -> int:
    try:
        return max(0, int(str(value).strip()))
    except Exception:
        return default_value


def _parse_process_meta(form) -> dict:
    names = form.getlist("process_name")
    icons = form.getlist("process_icon")
    colors = form.getlist("process_color")
    aliases = form.getlist("process_aliases")
    file_groups = form.getlist("process_file_groups")
    rows: list[dict] = []
    total = max(len(names), len(icons), len(colors), len(aliases), len(file_groups))
    for idx in range(total):
        name = (names[idx] if idx < len(names) else "").strip()
        if not name:
            continue
        rows.append(
            {
                "name": name,
                "icon": (icons[idx] if idx < len(icons) else "").strip(),
                "color": (colors[idx] if idx < len(colors) else "").strip(),
                "aliases": (aliases[idx] if idx < len(aliases) else "").strip(),
                "file_groups": (file_groups[idx] if idx < len(file_groups) else "").strip(),
            }
        )
    return sanitize_process_meta(rows)


def _saved_process_meta(form) -> dict:
    # Persist the effective library so defaults remain stable across reloads/restarts.
    submitted = _parse_process_meta(form)
    return sanitize_process_meta(load_process_meta(overrides=submitted or None))


def _active_process_meta(settings) -> dict:
    stored = getattr(settings, "process_meta", None) if settings else None
    return load_process_meta(overrides=stored or None)


def _process_rows_from_meta(process_meta: dict) -> list[dict]:
    rows = []
    for name, meta in (process_meta or {}).items():
        if str(name).startswith("_"):
            continue
        color = (meta or {}).get("color", "118, 113, 113")
        try:
            channels = [max(0, min(255, int(part.strip()))) for part in color.split(",")]
            color_hex = "#{:02x}{:02x}{:02x}".format(*channels) if len(channels) == 3 else "#767171"
        except Exception:
            color_hex = "#767171"
        rows.append(
            {
                "name": name,
                "icon": (meta or {}).get("icon", ""),
                "color": color,
                "color_hex": color_hex,
                "aliases": list((meta or {}).get("aliases") or []),
                "file_groups": list((meta or {}).get("file_groups") or []),
            }
        )
    rows.sort(key=lambda item: item["name"])
    return rows

bp = Blueprint("admin", __name__, url_prefix="/admin")

@bp.get("/")
@roles_required("admin")
def admin_index():
    return render_template("admin/index.html")

@bp.get("/metrics")
@roles_required("admin")
def admin_metrics():
    try:
        from app.services.metrics import get_metrics_store
        file_root = current_app.config.get("FILE_ROOT_LOCAL") or current_app.root_path
        metrics = get_metrics_store().snapshot(file_root=file_root)
    except Exception:
        metrics = {}
    return render_template("admin/metrics.html", metrics=metrics)


@bp.route("/settings", methods=["GET", "POST"])
@roles_required("admin")
def admin_settings():
    settings = get_app_settings(create=True)
    valid_timezones = set(timezone_choices())
    if request.method == "POST":
        recompute_processes = request.form.get("recompute_process_library") in ("1", "true", "on")
        submitted_timezone = (request.form.get("timezone") or "").strip()
        timezone_name = submitted_timezone if submitted_timezone in valid_timezones else "UTC"
        if submitted_timezone and submitted_timezone not in valid_timezones:
            flash("Invalid timezone submitted. Reverted to UTC.", "error")
        settings.timezone = timezone_name

        hw_raw = request.form.get("hardware_folders") or ""
        settings.hardware_folders = _parse_hw_folders(hw_raw)

        fp_raw = request.form.get("flat_pattern_page_names") or ""
        settings.flat_pattern_page_names = _parse_flat_pattern_names(fp_raw)
        
        settings.arena_file_link_base_url = (request.form.get("arena_file_link_base_url") or "").strip()

        settings.upload_pack_max_zip_mb = _parse_int(
            request.form.get("upload_pack_max_zip_mb"), settings.upload_pack_max_zip_mb or 1024
        )
        settings.upload_pack_max_file_mb = _parse_int(
            request.form.get("upload_pack_max_file_mb"), settings.upload_pack_max_file_mb or 1024
        )
        settings.upload_pack_max_files = _parse_int(
            request.form.get("upload_pack_max_files"), settings.upload_pack_max_files or 5000
        )
        if request.form.get("reset_process_library") in ("1", "true", "on"):
            settings.process_meta = {}
        else:
            settings.process_meta = _saved_process_meta(request.form)

        remove_logo = bool(request.form.get("remove_logo") in ("on", "true", "1", True))
        upload = request.files.get("brand_logo")
        if upload and upload.filename:
            raw = upload.read() or b""
            max_bytes = int(current_app.config.get("BRANDING_LOGO_MAX_BYTES", 2 * 1024 * 1024))
            if len(raw) > max_bytes:
                flash(f"Logo file too large (max {max_bytes} bytes).", "error")
                return redirect(url_for("admin.admin_settings"))
            ext = os.path.splitext(upload.filename)[1].lower()
            if ext not in (".png", ".svg"):
                flash("Logo must be a PNG or SVG file.", "error")
                return redirect(url_for("admin.admin_settings"))
            if ext == ".png" and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                flash("Invalid PNG file.", "error")
                return redirect(url_for("admin.admin_settings"))
            if ext == ".svg" and b"<svg" not in raw[:2048].lower():
                flash("Invalid SVG file.", "error")
                return redirect(url_for("admin.admin_settings"))
            brand_dir, base_root = branding_root()
            os.makedirs(brand_dir, exist_ok=True)
            target_name = f"logo{ext}"
            abs_path = os.path.join(brand_dir, target_name)
            with open(abs_path, "wb") as fh:
                fh.write(raw)
            try:
                rel_path = os.path.relpath(abs_path, base_root)
            except Exception:
                rel_path = abs_path
            settings.brand_logo_rel_path = rel_path
            remove_logo = False

        process_icon_upload = request.files.get("process_icon_upload")
        if process_icon_upload and process_icon_upload.filename:
            raw = process_icon_upload.read() or b""
            max_bytes = 2 * 1024 * 1024
            filename = secure_filename(process_icon_upload.filename)
            ext = os.path.splitext(filename)[1].lower()
            if not filename or filename.startswith("."):
                flash("Process icon needs a valid filename.", "error")
                return redirect(url_for("admin.admin_settings"))
            if len(raw) > max_bytes:
                flash("Process icon is too large (maximum 2 MB).", "error")
                return redirect(url_for("admin.admin_settings"))
            if ext not in (".png", ".svg"):
                flash("Process icon must be a PNG or SVG file.", "error")
                return redirect(url_for("admin.admin_settings"))
            if ext == ".png" and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                flash("Invalid process icon PNG.", "error")
                return redirect(url_for("admin.admin_settings"))
            if ext == ".svg" and not _safe_process_svg(raw):
                flash("Invalid process icon SVG.", "error")
                return redirect(url_for("admin.admin_settings"))
            image_root = os.path.join(current_app.root_path, "static", "images")
            os.makedirs(image_root, exist_ok=True)
            stem = os.path.splitext(filename)[0]
            candidate = filename
            suffix = 2
            while os.path.exists(os.path.join(image_root, candidate)):
                candidate = f"{stem}-{suffix}{ext}"
                suffix += 1
            filename = candidate
            with open(os.path.join(image_root, filename), "wb") as icon_file:
                icon_file.write(raw)
            flash(f"Process icon '{filename}' uploaded and is now available.", "success")

        if remove_logo:
            settings.brand_logo_rel_path = ""

        settings.updated_at = utc_now()
        settings.save()
        clear_timezone_cache()
        process_meta = _active_process_meta(settings)
        try:
            current_app.config["APP_TIMEZONE"] = timezone_name
            current_app.config["DEFAULT_TIMEZONE"] = timezone_name
            current_app.config["HARDWARE_FOLDERS"] = settings.hardware_folders or []
            current_app.config["FLAT_PATTERN_PAGE_NAMES"] = settings.flat_pattern_page_names or []
            current_app.config["UPLOAD_PACK_MAX_ZIP_MB"] = settings.upload_pack_max_zip_mb or 0
            current_app.config["UPLOAD_PACK_MAX_FILE_MB"] = settings.upload_pack_max_file_mb or 0
            current_app.config["UPLOAD_PACK_MAX_FILES"] = settings.upload_pack_max_files or 0
            current_app.config["ARENA_FILE_LINK_BASE_URL"] = settings.arena_file_link_base_url or ""
            from app.services.app_settings import resolve_file_sources
            file_sources = resolve_file_sources(settings)
            current_app.config["PROCESS_META"] = process_meta
            current_app.config["FILE_SOURCES"] = file_sources
            if file_sources:
                primary_source = file_sources[0]
                current_app.config["FILES_LOCAL_ROOT"] = primary_source.get("local_root") or ""
                current_app.config["FILE_ROOT_LOCAL"] = primary_source.get("local_root") or ""
                current_app.config["FILES_URL_PREFIX"] = primary_source.get("url_prefix") or ""
                current_app.config["FILE_ROOT_HTTP"] = primary_source.get("url_prefix") or ""
                current_app.config["EXTRA_FILES_ROOT"] = primary_source.get("local_root") or ""
        except Exception:
            pass
        try:
            log_action("admin.settings.update", resource_type="settings", resource="app_settings")
        except Exception:
            pass

        if recompute_processes:
            try:
                from app.services.canonical_fields import rebuild_all_part_canonical_fields
                from app.services.part_materialized import rebuild_part_materialized_fields

                canonical_report = rebuild_all_part_canonical_fields(process_meta=process_meta)
                materialized_report = rebuild_part_materialized_fields()
                errors = int(materialized_report.get("errors") or 0)
                status = "warning" if errors else "success"
                flash(
                    "Settings updated. Recomputed existing parts: "
                    f"scanned={canonical_report.get('scanned', 0)}, "
                    f"process/canonical updates={canonical_report.get('updated', 0)}, "
                    f"materialized updates={materialized_report.get('updated', 0)}, "
                    f"errors={errors}.",
                    status,
                )
                try:
                    log_action(
                        "admin.settings.process_recompute",
                        resource_type="settings",
                        resource=(
                            f"scanned={canonical_report.get('scanned', 0)},"
                            f"updated={canonical_report.get('updated', 0)},"
                            f"materialized={materialized_report.get('updated', 0)},"
                            f"errors={errors}"
                        ),
                    )
                except Exception:
                    pass
            except Exception as exc:
                try:
                    current_app.logger.exception("Process library recompute failed")
                except Exception:
                    pass
                flash(f"Settings saved, but process recompute failed: {exc}", "error")
        else:
            flash("Settings updated.", "success")
        return redirect(url_for("admin.admin_settings"))

    process_meta = _active_process_meta(settings)
    current_app.config["PROCESS_META"] = process_meta
    process_rows = _process_rows_from_meta(process_meta)
    image_root = os.path.join(current_app.root_path, "static", "images")
    process_icon_choices = sorted(
        [
            name
            for name in os.listdir(image_root)
            if os.path.isfile(os.path.join(image_root, name)) and name.lower().endswith((".svg", ".png"))
        ]
    ) if os.path.isdir(image_root) else []
    hw_display = "\n".join(settings.hardware_folders or [])
    fp_display = "\n".join(settings.flat_pattern_page_names or [])
    return render_template(
        "admin/settings.html",
        settings=settings,
        timezone_choices=timezone_choices(),
        selected_timezone=resolve_timezone_name(),
        timezone_display_now=format_display_ts(utc_now(), fmt="%Y-%m-%d %H:%M:%S %Z"),
        process_rows=process_rows,
        process_icon_choices=process_icon_choices,
        hardware_folders_text=hw_display,
        flat_pattern_page_names_text=fp_display,
        process_file_group_choices=[
            ("pdf", "PDF drawing"),
            ("datasheet", "Datasheet"),
            ("png", "Preview image"),
            ("step", "STEP model"),
            ("dxf", "DXF flat pattern"),
            ("edr", "eDrawings"),
            ("3mf", "3MF model"),
        ],
    )

@bp.route("/users")
@roles_required("admin")
def users_list():
    users = User.objects().order_by("-id").limit(200)
    return render_template("admin/users_list.html", users=users)


def _cleanup_user_references(u: User):
    try:
        Job.objects(participants=u).update(pull__participants=u)
    except Exception:
        pass
    try:
        Supplier.objects(users=u).update(pull__users=u)
    except Exception:
        pass
    try:
        Customer.objects(users=u).update(pull__users=u)
    except Exception:
        pass
    try:
        ApiToken.objects(user_id=u).delete()
    except Exception:
        pass
    try:
        UserSettings.objects(user_id=u).delete()
    except Exception:
        pass


@bp.post("/users/bulk-delete")
@roles_required("admin")
def users_bulk_delete():
    ids = request.form.getlist("user_ids")
    if not ids:
        flash("No users selected.", "error")
        return redirect(url_for("admin.users_list"))
    users = list(User.objects(id__in=ids))
    deleted = 0
    skipped_admin = 0
    skipped_self = 0
    for u in users:
        try:
            if u.has_role("admin"):
                skipped_admin += 1
                continue
        except Exception:
            pass
        try:
            if str(u.id) == str(current_user.id):
                skipped_self += 1
                continue
        except Exception:
            pass
        _cleanup_user_references(u)
        try:
            u.delete()
            deleted += 1
            try:
                log_action("admin.user.delete", resource_type="user", resource=str(u.email))
            except Exception:
                pass
        except Exception:
            pass
    if deleted:
        flash(f"Deleted {deleted} user(s).", "success")
    if skipped_admin:
        flash(f"Skipped {skipped_admin} admin user(s).", "warning")
    if skipped_self:
        flash("Skipped your own account.", "warning")
    return redirect(url_for("admin.users_list"))

@bp.route("/users/new", methods=["GET", "POST"])
@roles_required("admin")
def users_create():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not email or not password:
            flash("Email and password are required.", "error")
            return redirect(url_for("admin.users_create"))
        for error in validate_admin_password(password, email=email):
            flash(error, "error")
            return redirect(url_for("admin.users_create"))
        if User.objects(email=email).first():
            flash("User already exists.", "error")
            return redirect(url_for("admin.users_create"))
        import secrets
        u = User(
            email=email,
            password=hash_password(password),
            fs_uniquifier=secrets.token_hex(16),
            password_changed_at=utc_now(),
            updated_at=utc_now(),
        )
        # initial roles from form
        role_ids = request.form.getlist("roles")
        if role_ids:
            u.roles = list(Role.objects(id__in=role_ids))
        u.save()
        try:
            log_action("admin.user.create", resource_type="user", resource=email)
        except Exception:
            pass
        flash("User created.", "success")
        return redirect(url_for("admin.users_list"))
    roles = Role.objects().order_by("name")
    return render_template("admin/users_form.html", roles=roles)

@bp.route("/users/<user_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def users_edit(user_id):
    # robust fetch: 404 if id is invalid or user doesn't exist
    try:
        u = User.objects.get(id=user_id)
    except (DoesNotExist, ValidationError):
        abort(404)

    if request.method == "POST":
        role_ids = request.form.getlist("roles")
        # optional: filter out invalid ids so we don't error on bad input
        try:
            u.roles = list(Role.objects(id__in=role_ids))
        except ValidationError:
            # if any id is malformed, ignore them (or flash an error if you prefer)
            u.roles = list(Role.objects(id__in=[rid for rid in role_ids if len(rid) == 24]))

        # Optional password reset
        new_pw = (request.form.get("new_password") or "").strip()
        new_pw2 = (request.form.get("confirm_password") or "").strip()
        if new_pw or new_pw2:
            if not new_pw:
                flash("New password cannot be empty.", "error");
                return redirect(url_for("admin.users_edit", user_id=user_id))
            if new_pw != new_pw2:
                flash("Password confirmation does not match.", "error");
                return redirect(url_for("admin.users_edit", user_id=user_id))
            for error in validate_admin_password(new_pw, email=u.email or ""):
                flash(error, "error")
                return redirect(url_for("admin.users_edit", user_id=user_id))
            u.password = hash_password(new_pw)
            u.password_changed_at = utc_now()
            try:
                log_action("admin.user.password", resource_type="user", resource=str(u.email))
            except Exception:
                pass

        u.updated_at = utc_now()
        u.save()
        try:
            log_action("admin.user.edit_roles", resource_type="user", resource=str(u.email))
        except Exception:
            pass
        flash("User updated.", "success")
        return redirect(url_for("admin.users_list"))

    roles = Role.objects().order_by("name")
    return render_template("admin/users_edit.html", user=u, roles=roles)


@bp.route("/purge-parts", methods=["GET", "POST"])
@require_permission("parts.purge")
def purge_parts():
    """Dangerous action: delete all Parts, BOM links, and PartFiles.
    Requires admin and explicit POST with CSRF.
    """
    if request.method == "POST":
        # Import here to avoid circulars at import time
        from ..models.part import Part
        from ..models.bom import BOMLink
        from ..models.artifact import PartFile

        n_files = PartFile.objects.delete()
        n_bom   = BOMLink.objects.delete()
        n_parts = Part.objects.delete()

        try:
            log_action("admin.purge_parts", resource_type="system", resource=f"parts={n_parts},bom={n_bom},files={n_files}")
        except Exception:
            pass
        flash(f"Deleted parts={n_parts}, bom_links={n_bom}, part_files={n_files}", "success")
        return redirect(url_for("admin.users_list"))

    return render_template("admin/purge_parts.html")
