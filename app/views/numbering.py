from __future__ import annotations

from flask import Blueprint, request, jsonify
from flask_security import current_user
from mongoengine.errors import NotUniqueError, DoesNotExist, ValidationError

from app.extensions import csrf
from app.models.numbering import NumberingScheme, NumberingCounter
from app.models.user_settings import UserSettings
from app.services.acl import user_has_permission
from app.services.api_auth import api_auth_required, get_request_user
from app.services.numbering import (
    normalize_scheme_payload,
    validate_scheme_definition,
    scheme_to_dict,
    preview_number,
    allocate_number,
    revision_for_existing,
)
from app.models.part import Part
from app.models.part_revision import PartRevisionHistory

bp = Blueprint("numbering_api", __name__, url_prefix="/api/numbering")


def _role_names(user) -> set[str]:
    names = set()
    try:
        for r in (user.roles or []):
            n = getattr(r, "name", None)
            if n:
                names.add(str(n))
    except Exception:
        pass
    return names


def _can_manage(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    roles = _role_names(user)
    if "admin" in roles or "manager" in roles:
        return True
    return user_has_permission(user, "numbering.manage")


def _json_error(code: str, message: str, details=None, status: int = 400):
    return jsonify({
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        }
    }), status


@bp.get("/schemes")
@api_auth_required
@csrf.exempt
def list_schemes():
    user = get_request_user()
    if _can_manage(user):
        queryset = NumberingScheme.objects()
    else:
        queryset = NumberingScheme.objects(is_active=True)
    schemes = [scheme_to_dict(s) for s in queryset.order_by("name")]
    return jsonify({"ok": True, "schemes": schemes})


@bp.post("/schemes")
@api_auth_required
@csrf.exempt
def create_scheme():
    user = get_request_user()
    if not _can_manage(user):
        return _json_error("forbidden", "Not authorized.", status=403)
    payload = request.get_json(force=True, silent=True) or {}
    scheme_data, errors = normalize_scheme_payload(
        payload,
        getattr(user, "email", None),
        None,
        require_name=True,
        allow_admin_flags=True,
    )
    v_errors, v_warnings, example = validate_scheme_definition(scheme_data)
    errors.extend(v_errors)
    if errors:
        return _json_error("validation_failed", "Scheme validation failed.", errors, status=400)

    try:
        scheme = NumberingScheme(**scheme_data).save()
    except NotUniqueError:
        return _json_error("duplicate", "Scheme name already exists.", status=409)

    return jsonify({
        "ok": True,
        "scheme": scheme_to_dict(scheme),
        "warnings": v_warnings,
        "example": example,
    })


@bp.get("/schemes/<scheme_id>")
@api_auth_required
@csrf.exempt
def get_scheme(scheme_id: str):
    try:
        scheme = NumberingScheme.objects.get(id=scheme_id)
    except (DoesNotExist, ValidationError):
        return _json_error("not_found", "Scheme not found.", status=404)
    user = get_request_user()
    if not scheme.is_active and not _can_manage(user):
        return _json_error("inactive", "Scheme is inactive.", status=403)
    return jsonify({"ok": True, "scheme": scheme_to_dict(scheme)})


@bp.put("/schemes/<scheme_id>")
@api_auth_required
@csrf.exempt
def update_scheme(scheme_id: str):
    user = get_request_user()
    if not _can_manage(user):
        return _json_error("forbidden", "Not authorized.", status=403)
    try:
        scheme = NumberingScheme.objects.get(id=scheme_id)
    except (DoesNotExist, ValidationError):
        return _json_error("not_found", "Scheme not found.", status=404)

    payload = request.get_json(force=True, silent=True) or {}
    scheme_data, errors = normalize_scheme_payload(
        payload,
        getattr(user, "email", None),
        scheme,
        require_name=True,
        allow_admin_flags=True,
    )
    v_errors, v_warnings, example = validate_scheme_definition(scheme_data)
    errors.extend(v_errors)
    if errors:
        return _json_error("validation_failed", "Scheme validation failed.", errors, status=400)

    for key in (
        "name", "description", "is_active", "is_preset", "is_recommended", "visibility",
        "pattern_segments", "separator", "scope_mode", "scope_keys",
        "seq", "revision", "validation_rules", "audit",
    ):
        setattr(scheme, key, scheme_data[key])

    try:
        scheme.save()
    except NotUniqueError:
        return _json_error("duplicate", "Scheme name already exists.", status=409)

    return jsonify({
        "ok": True,
        "scheme": scheme_to_dict(scheme),
        "warnings": v_warnings,
        "example": example,
    })


@bp.delete("/schemes/<scheme_id>")
@api_auth_required
@csrf.exempt
def delete_scheme(scheme_id: str):
    user = get_request_user()
    if not _can_manage(user):
        return _json_error("forbidden", "Not authorized.", status=403)
    try:
        scheme = NumberingScheme.objects.get(id=scheme_id)
    except (DoesNotExist, ValidationError):
        return _json_error("not_found", "Scheme not found.", status=404)

    scheme_id_text = str(scheme.id)
    UserSettings.objects(default_scheme_id=scheme_id_text).update(set__default_scheme_id="")
    NumberingCounter.objects(counter_key__startswith=f"scheme:{scheme_id_text}|").delete()
    NumberingScheme.objects(id=scheme.id).delete()

    return jsonify({"ok": True, "deleted_scheme_id": scheme_id_text})


@bp.post("/schemes/validate")
@api_auth_required
@csrf.exempt
def validate_scheme():
    user = get_request_user()
    if not _can_manage(user):
        return _json_error("forbidden", "Not authorized.", status=403)
    payload = request.get_json(force=True, silent=True) or {}
    scheme_data, errors = normalize_scheme_payload(
        payload,
        getattr(user, "email", None),
        None,
        require_name=False,
        allow_admin_flags=_can_manage(user),
    )
    v_errors, v_warnings, example = validate_scheme_definition(scheme_data)
    errors.extend(v_errors)
    if errors:
        return jsonify({
            "ok": False,
            "error": {"code": "validation_failed", "message": "Scheme validation failed.", "details": errors},
            "warnings": v_warnings,
            "example": example,
        }), 400
    return jsonify({"ok": True, "warnings": v_warnings, "example": example})


@bp.post("/preview")
@api_auth_required
@csrf.exempt
def preview():
    payload = request.get_json(force=True, silent=True) or {}
    scheme_id = str(payload.get("scheme_id") or "").strip()
    if not scheme_id:
        return _json_error("missing_scheme", "scheme_id is required.")
    try:
        scheme = NumberingScheme.objects.get(id=scheme_id)
    except (DoesNotExist, ValidationError):
        return _json_error("not_found", "Scheme not found.", status=404)
    if not scheme.is_active:
        return _json_error("inactive", "Scheme is inactive.", status=400)

    result, errors = preview_number(scheme, payload.get("context") or {}, payload.get("sequence_values"))
    if errors:
        return _json_error("validation_failed", "Preview failed.", errors, status=400)
    return jsonify({"ok": True, **result})


@bp.post("/allocate")
@api_auth_required
@csrf.exempt
def allocate():
    payload = request.get_json(force=True, silent=True) or {}
    scheme_id = str(payload.get("scheme_id") or "").strip()
    if not scheme_id:
        return _json_error("missing_scheme", "scheme_id is required.")
    try:
        scheme = NumberingScheme.objects.get(id=scheme_id)
    except (DoesNotExist, ValidationError):
        return _json_error("not_found", "Scheme not found.", status=404)
    if not scheme.is_active:
        return _json_error("inactive", "Scheme is inactive.", status=400)

    create_part_if_missing = payload.get("create_part_if_missing", True)
    action = payload.get("requested_revision_action") or "new_part"
    existing_part_number = payload.get("existing_part_number")
    cad_ref = payload.get("cad_ref") or None

    result, errors = allocate_number(
        scheme,
        payload.get("context") or {},
        bool(create_part_if_missing),
        action,
        existing_part_number,
        getattr(get_request_user(), "email", None),
        cad_ref,
        payload.get("sequence_values"),
    )
    if errors:
        return _json_error("allocation_failed", "Allocation failed.", errors, status=400)
    return jsonify({"ok": True, **result})


@bp.post("/parts/<part_number>/revise")
@api_auth_required
@csrf.exempt
def revise_part(part_number: str):
    payload = request.get_json(force=True, silent=True) or {}
    part = Part.objects(part_number=part_number).order_by("-updated_at").first()
    if not part:
        return _json_error("not_found", "Part not found.", status=404)

    scheme_id = str(payload.get("scheme_id") or "").strip()
    scheme = None
    if scheme_id:
        try:
            scheme = NumberingScheme.objects.get(id=scheme_id)
        except (DoesNotExist, ValidationError):
            return _json_error("not_found", "Scheme not found.", status=404)

    policy = "alpha"
    start = "A"
    if scheme is not None:
        policy = str((scheme.revision or {}).get("policy") or policy)
        start = str((scheme.revision or {}).get("start") or start)

    new_rev = revision_for_existing(part.revision, policy, start)
    if Part.objects(part_number=part.part_number, revision=new_rev).first():
        return _json_error("duplicate", "Revision already exists.", status=409)

    cloned = Part(
        part_number=part.part_number,
        revision=new_rev,
        description=part.description or "",
        processes=list(part.processes or []),
        category=part.category or "",
        uom=part.uom or "EA",
        manufacturer=part.manufacturer or "",
        mfr_part=part.mfr_part or "",
        status=part.status or "active",
        docs=list(part.docs or []),
        attrs=dict(part.attrs or {}),
    )
    cloned.attrs["revision"] = new_rev
    cloned.save()

    user = get_request_user()
    PartRevisionHistory(
        part_id=cloned,
        part_number=cloned.part_number,
        revision=new_rev,
        status="WIP",
        change_note=str(payload.get("change_note") or "Revision via API"),
        created_by=getattr(user, "email", None) or "",
    ).save()

    return jsonify({"ok": True, "part_number": cloned.part_number, "revision": new_rev})
