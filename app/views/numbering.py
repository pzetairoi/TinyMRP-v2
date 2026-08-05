from __future__ import annotations

from flask import Blueprint, request, jsonify
from mongoengine.errors import NotUniqueError, DoesNotExist, ValidationError

from app.extensions import csrf
from app.models.numbering import NumberingScheme, NumberingCounter
from app.models.user_settings import UserSettings
from app.services.acl import user_has_permission
from app.services.audit import log_action
from app.services.authorization import scope_queryset
from app.services.api_auth import api_auth_required, get_request_user
from app.services.numbering import (
    normalize_scheme_payload,
    validate_scheme_definition,
    scheme_to_dict,
    latest_part_numbers_by_scheme,
    preview_number,
    allocate_number,
    revision_for_existing,
)
from app.models.part import Part
from app.models.part_revision import PartRevisionHistory

bp = Blueprint("numbering_api", __name__, url_prefix="/api/numbering")


def _can_manage(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and user_has_permission(user, "numbering.manage")
    )


def _can_use_active_schemes(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and (
            user_has_permission(user, "numbering.allocate")
            or user_has_permission(user, "parts.create")
        )
    )


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
    elif _can_use_active_schemes(user):
        queryset = NumberingScheme.objects(is_active=True)
    else:
        return _json_error("forbidden", "Not authorized.", status=403)
    scheme_docs = list(queryset.order_by("name"))
    latest_numbers = latest_part_numbers_by_scheme(scheme_docs)
    schemes = []
    for scheme in scheme_docs:
        data = scheme_to_dict(scheme)
        data["last_part_number"] = latest_numbers.get(str(scheme.id), "")
        schemes.append(data)
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
    if not _can_manage(user) and not _can_use_active_schemes(user):
        return _json_error("forbidden", "Not authorized.", status=403)
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
    user = get_request_user()
    if not _can_use_active_schemes(user):
        return _json_error("forbidden", "Not authorized.", status=403)
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
    user = get_request_user()
    if not user_has_permission(user, "numbering.allocate"):
        return _json_error("forbidden", "Not authorized.", status=403)
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
    action = str(payload.get("requested_revision_action") or "new_part").strip().lower()
    existing_part_number = payload.get("existing_part_number")
    cad_ref = payload.get("cad_ref") or None
    create_requested = bool(create_part_if_missing)
    source_revision = None
    if action == "new_part" and create_requested:
        if not user_has_permission(user, "parts.create"):
            return _json_error("forbidden", "Not authorized.", status=403)
    elif action in {"keep_existing", "revise_existing"}:
        if not existing_part_number:
            existing_part_number = (payload.get("context") or {}).get("part_number")
        source_query = scope_queryset(Part.objects, user, "parts")
        source = source_query.filter(
            part_number__iexact=str(existing_part_number or "").strip()
        ).order_by("-updated_at").first()
        if not source:
            return _json_error("not_found", "Part not found.", status=404)
        source_revision = str(source.revision or "").strip()
        if action == "revise_existing" and not user_has_permission(user, "parts.revise"):
            return _json_error("forbidden", "Not authorized.", status=403)

    result, errors = allocate_number(
        scheme,
        payload.get("context") or {},
        bool(create_part_if_missing),
        action,
        existing_part_number,
        getattr(user, "email", None),
        cad_ref,
        payload.get("sequence_values"),
        source_revision,
    )
    if errors:
        return _json_error("allocation_failed", "Allocation failed.", errors, status=400)
    try:
        log_action(
            "numbering.allocate",
            resource_type="part",
            resource=f"{result.get('part_number', '')}:{result.get('revision', '')}",
            meta={"action": str(action), "created_part": bool(result.get("part_id"))},
        )
    except Exception:
        pass
    return jsonify({"ok": True, **result})


@bp.post("/parts/<part_number>/revise")
@api_auth_required
@csrf.exempt
def revise_part(part_number: str):
    payload = request.get_json(force=True, silent=True) or {}
    user = get_request_user()
    if not user_has_permission(user, "parts.revise"):
        return _json_error("forbidden", "Not authorized.", status=403)
    part = scope_queryset(Part.objects, user, "parts").filter(
        part_number__iexact=part_number
    ).order_by("-updated_at").first()
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
        docs=[],
        attrs=_revision_attrs(part.attrs, new_rev),
    )
    cloned.save()

    PartRevisionHistory(
        part_id=cloned,
        part_number=cloned.part_number,
        revision=new_rev,
        status="WIP",
        change_note=str(payload.get("change_note") or "Revision via API"),
        created_by=getattr(user, "email", None) or "",
    ).save()
    try:
        log_action(
            "part.revise",
            resource_type="part",
            resource=f"{cloned.part_number}:{new_rev}",
            meta={"source_revision": str(part.revision or "")},
        )
    except Exception:
        pass

    return jsonify({"ok": True, "part_number": cloned.part_number, "revision": new_rev})


def _revision_attrs(raw_attrs, revision: str) -> dict:
    protected_tokens = {
        "approved",
        "approvedby",
        "approveddate",
        "approvalactor",
        "approvaltimestamp",
        "released",
        "releasedby",
        "releasedat",
        "releaseactor",
        "releasetimestamp",
        "createdby",
        "updatedby",
        "auditactor",
    }
    attrs = {
        key: value
        for key, value in dict(raw_attrs or {}).items()
        if "".join(ch for ch in str(key).casefold() if ch.isalnum())
        not in protected_tokens
    }
    attrs["revision"] = revision
    return attrs
