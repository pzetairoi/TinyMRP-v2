from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple
import re

from pymongo import ReturnDocument
from mongoengine.errors import NotUniqueError

from app.models.numbering import NumberingCounter, NumberingScheme
from app.models.part import Part
from app.models.part_revision import PartRevisionHistory


ALLOWED_SCOPE_MODES = {"global", "by_type", "by_project", "by_family", "custom_keys"}
ALLOWED_RESET_POLICIES = {"never", "yearly", "monthly", "by_project"}
ALLOWED_REV_POLICIES = {"alpha", "numeric", "none"}
ALLOWED_DATE_FORMATS = {"YYYY", "YY", "MM", "YYYYMM"}
ALLOWED_FIELD_CASING = {"upper", "lower", "none"}


DEFAULT_SEQ = {
    "padding": 6,
    "base": 10,
    "start_at": 1,
    "reset_policy": "never",
}

DEFAULT_REVISION = {
    "policy": "alpha",
    "start": "A",
}

DEFAULT_VALIDATION = {
    "max_length": 32,
    "allowed_charset": "A-Z0-9-",
    "require_seq_segment": True,
}


def normalize_scheme_payload(
    payload: Dict[str, Any],
    user_email: str | None,
    existing: NumberingScheme | None,
    require_name: bool = True,
    allow_admin_flags: bool = False,
) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    data = dict(payload or {})

    name = str(data.get("name") or (existing.name if existing else "")).strip()
    if require_name and not name:
        errors.append("Name is required.")

    description = str(data.get("description") or (existing.description if existing else "")).strip()
    is_active = data.get("is_active")
    if is_active is None:
        is_active = existing.is_active if existing is not None else True
    is_active = bool(is_active)

    is_preset = existing.is_preset if existing is not None else False
    is_recommended = existing.is_recommended if existing is not None else False
    visibility = existing.visibility if existing is not None else "advanced_only"
    if allow_admin_flags:
        if "is_preset" in data:
            is_preset = bool(data.get("is_preset"))
        if "is_recommended" in data:
            is_recommended = bool(data.get("is_recommended"))
        if "visibility" in data:
            visibility = str(data.get("visibility") or visibility)

    separator = str(data.get("separator") or (existing.separator if existing else "-"))
    scope_mode = str(data.get("scope_mode") or (existing.scope_mode if existing else "global")).strip()
    scope_keys = data.get("scope_keys") or (existing.scope_keys if existing else [])
    if not isinstance(scope_keys, list):
        scope_keys = [str(scope_keys)]
    scope_keys = [str(k).strip() for k in scope_keys if str(k).strip()]

    seq = dict(DEFAULT_SEQ)
    seq.update(existing.seq if existing is not None and isinstance(existing.seq, dict) else {})
    seq.update(data.get("seq") or {})
    seq["padding"] = _coerce_int(seq.get("padding"), DEFAULT_SEQ["padding"])
    seq["base"] = _coerce_int(seq.get("base"), DEFAULT_SEQ["base"])
    seq["start_at"] = _coerce_int(seq.get("start_at"), DEFAULT_SEQ["start_at"])
    seq["auto_sequence_index"] = _coerce_int(seq.get("auto_sequence_index"), 0)
    seq["reset_policy"] = str(seq.get("reset_policy") or DEFAULT_SEQ["reset_policy"]).strip()

    revision = dict(DEFAULT_REVISION)
    revision.update(existing.revision if existing is not None and isinstance(existing.revision, dict) else {})
    revision.update(data.get("revision") or {})
    revision["policy"] = str(revision.get("policy") or DEFAULT_REVISION["policy"]).strip()
    revision["start"] = str(revision.get("start") or DEFAULT_REVISION["start"]).strip()

    validation_rules = dict(DEFAULT_VALIDATION)
    validation_rules.update(existing.validation_rules if existing is not None and isinstance(existing.validation_rules, dict) else {})
    validation_rules.update(data.get("validation_rules") or {})
    validation_rules["max_length"] = _coerce_int(validation_rules.get("max_length"), DEFAULT_VALIDATION["max_length"])
    validation_rules["allowed_charset"] = str(validation_rules.get("allowed_charset") or DEFAULT_VALIDATION["allowed_charset"]).strip()
    validation_rules["require_seq_segment"] = _coerce_bool(validation_rules.get("require_seq_segment"), DEFAULT_VALIDATION["require_seq_segment"])

    pattern_segments = _normalize_segments(data.get("pattern_segments") or (existing.pattern_segments if existing else []), errors)

    now = datetime.utcnow()
    audit = dict(existing.audit) if existing is not None and isinstance(existing.audit, dict) else {}
    if not audit.get("created_at"):
        audit["created_at"] = now
    if not audit.get("created_by") and user_email:
        audit["created_by"] = user_email
    audit["updated_at"] = now
    if user_email:
        audit["updated_by"] = user_email

    scheme = {
        "name": name,
        "description": description,
        "is_active": is_active,
        "is_preset": is_preset,
        "is_recommended": is_recommended,
        "visibility": visibility,
        "pattern_segments": pattern_segments,
        "separator": separator,
        "scope_mode": scope_mode,
        "scope_keys": scope_keys,
        "seq": seq,
        "revision": revision,
        "validation_rules": validation_rules,
        "audit": audit,
    }

    return scheme, errors


def validate_scheme_definition(scheme: Dict[str, Any], context: Dict[str, Any] | None = None) -> Tuple[List[str], List[str], Dict[str, str]]:
    errors: List[str] = []
    warnings: List[str] = []

    scope_mode = str(scheme.get("scope_mode") or "global")
    if scope_mode not in ALLOWED_SCOPE_MODES:
        errors.append("scope_mode must be one of: " + ", ".join(sorted(ALLOWED_SCOPE_MODES)))

    seq = scheme.get("seq") or {}
    start_at = _coerce_int(seq.get("start_at"), DEFAULT_SEQ["start_at"])
    if start_at <= 0:
        errors.append("seq.start_at must be > 0.")

    reset_policy = str(seq.get("reset_policy") or DEFAULT_SEQ["reset_policy"])
    if reset_policy not in ALLOWED_RESET_POLICIES:
        errors.append("seq.reset_policy must be one of: " + ", ".join(sorted(ALLOWED_RESET_POLICIES)))

    rev = scheme.get("revision") or {}
    rev_policy = str(rev.get("policy") or DEFAULT_REVISION["policy"])
    if rev_policy not in ALLOWED_REV_POLICIES:
        errors.append("revision.policy must be one of: " + ", ".join(sorted(ALLOWED_REV_POLICIES)))

    segments = scheme.get("pattern_segments") or []
    if not segments:
        errors.append("pattern_segments cannot be empty.")

    require_seq = _coerce_bool((scheme.get("validation_rules") or {}).get("require_seq_segment"), True)
    if require_seq and not any(str(s.get("kind") or "").lower() == "seq" for s in segments):
        errors.append("pattern_segments must include at least one seq segment.")

    seq_segments = _sequence_segments(segments)
    auto_seq_errors: List[str] = []
    auto_seq_index = _get_auto_sequence_index(scheme, seq_segments, auto_seq_errors)
    errors.extend(auto_seq_errors)

    for idx, seg in enumerate(segments):
        if not isinstance(seg, dict):
            errors.append(f"segment[{idx}] must be an object.")
            continue
        kind = str(seg.get("kind") or "").lower().strip()
        if kind not in ("literal", "field", "seq", "date"):
            errors.append(f"segment[{idx}].kind must be literal, field, seq, or date.")
            continue
        if kind == "literal" and not str(seg.get("value") or "").strip():
            errors.append(f"segment[{idx}] literal requires value.")
        if kind == "field":
            if not str(seg.get("field") or "").strip():
                errors.append(f"segment[{idx}] field requires field name.")
            casing = str(seg.get("casing") or "upper").lower()
            if casing not in ALLOWED_FIELD_CASING:
                errors.append(f"segment[{idx}] field casing must be upper, lower, or none.")
        if kind == "seq":
            padding = _coerce_int(seg.get("padding"), _coerce_int(seq.get("padding"), DEFAULT_SEQ["padding"]))
            base = _coerce_int(seg.get("base"), _coerce_int(seq.get("base"), DEFAULT_SEQ["base"]))
            start_value = _coerce_int(seg.get("start_at"), start_at)
            if padding <= 0:
                errors.append(f"segment[{idx}] seq padding must be > 0.")
            if base not in (10, 36):
                errors.append(f"segment[{idx}] seq base must be 10 or 36.")
            if start_value <= 0:
                errors.append(f"segment[{idx}] seq start_at must be > 0.")
        if kind == "date":
            fmt = str(seg.get("fmt") or "").strip()
            if fmt not in ALLOWED_DATE_FORMATS:
                errors.append(f"segment[{idx}] date fmt must be one of: {', '.join(sorted(ALLOWED_DATE_FORMATS))}.")

    if errors:
        return errors, warnings, {}

    example_context = context or _example_context_from_scheme(segments)
    sequence_values = _resolve_sequence_values(scheme, None)
    if auto_seq_index >= 0 and auto_seq_index < len(sequence_values):
        sequence_values[auto_seq_index] = start_at
    candidate, cand_errors, cand_warnings = build_candidate_number(scheme, example_context, sequence_values, datetime.utcnow())
    errors.extend(cand_errors)
    warnings.extend(cand_warnings)

    rev_value = revision_for_new_part(rev_policy, str(rev.get("start") or DEFAULT_REVISION["start"]))
    example = {
        "part_number_example": candidate or "",
        "revision_example": rev_value,
    }
    return errors, warnings, example


def build_candidate_number(
    scheme: Dict[str, Any],
    context: Dict[str, Any],
    sequence_values: List[int] | None,
    now: datetime,
) -> Tuple[str, List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    ctx = _normalize_context(context)
    separator = str(scheme.get("separator") or "-")
    seq_defaults = scheme.get("seq") or {}
    segments = scheme.get("pattern_segments") or []
    resolved_sequence_values = list(sequence_values or [])
    sequence_index = 0
    parts: List[str] = []

    for seg in segments:
        if not isinstance(seg, dict):
            errors.append("segment must be an object.")
            continue
        kind = str(seg.get("kind") or "").lower().strip()
        if kind == "literal":
            parts.append(str(seg.get("value") or "").strip())
        elif kind == "field":
            field = str(seg.get("field") or "").strip().lower()
            if not field:
                errors.append("field segment missing field name.")
                continue
            value = ctx.get(field, "")
            if not value:
                errors.append(f"context missing field '{field}'.")
                continue
            casing = str(seg.get("casing") or "upper").lower()
            value = _apply_casing(value, casing)
            pad_left = seg.get("pad_left")
            pad_char = str(seg.get("pad_char") or "0")[:1]
            if pad_left is not None:
                value = value.rjust(_coerce_int(pad_left, 0), pad_char)
            parts.append(value)
        elif kind == "seq":
            padding = _coerce_int(seg.get("padding"), _coerce_int(seq_defaults.get("padding"), DEFAULT_SEQ["padding"]))
            base = _coerce_int(seg.get("base"), _coerce_int(seq_defaults.get("base"), DEFAULT_SEQ["base"]))
            if base not in (10, 36):
                errors.append("seq base must be 10 or 36.")
                continue
            seq_start = _coerce_int(seg.get("start_at"), _coerce_int(seq_defaults.get("start_at"), DEFAULT_SEQ["start_at"]))
            seq_value = resolved_sequence_values[sequence_index] if sequence_index < len(resolved_sequence_values) else seq_start
            parts.append(_format_sequence(seq_value, padding, base))
            sequence_index += 1
        elif kind == "date":
            fmt = str(seg.get("fmt") or "").strip()
            if fmt not in ALLOWED_DATE_FORMATS:
                errors.append("date fmt must be one of YYYY, YY, MM, YYYYMM.")
                continue
            parts.append(_format_date(now, fmt))
        else:
            errors.append(f"Unknown segment kind '{kind}'.")

    if errors:
        return "", errors, warnings

    candidate = separator.join(parts) if separator else "".join(parts)
    rules = scheme.get("validation_rules") or {}
    max_length = _coerce_int(rules.get("max_length"), DEFAULT_VALIDATION["max_length"])
    if max_length > 0 and len(candidate) > max_length:
        errors.append(f"part number exceeds max_length ({max_length}).")

    allowed = str(rules.get("allowed_charset") or DEFAULT_VALIDATION["allowed_charset"]).strip()
    regex = _allowed_charset_regex(allowed)
    if candidate and regex and not regex.match(candidate):
        errors.append("part number contains characters outside allowed_charset.")

    return candidate, errors, warnings


def build_scope_key(scheme: Dict[str, Any], context: Dict[str, Any]) -> Tuple[str, List[str]]:
    errors: List[str] = []
    ctx = _normalize_context(context)
    mode = str(scheme.get("scope_mode") or "global")

    if mode == "global":
        return "global", errors
    if mode == "by_type":
        return _require_ctx_key(ctx, "type", errors, "type"), errors
    if mode == "by_project":
        return _require_ctx_key(ctx, "project", errors, "project"), errors
    if mode == "by_family":
        return _require_ctx_key(ctx, "family", errors, "family"), errors
    if mode == "custom_keys":
        keys = scheme.get("scope_keys") or []
        if not keys:
            errors.append("scope_keys is required for custom_keys mode.")
            return "", errors
        parts = []
        for k in keys:
            key = str(k).strip().lower()
            if not key:
                continue
            val = ctx.get(key, "")
            if not val:
                errors.append(f"context missing field '{key}'.")
                continue
            parts.append(f"{key}:{_apply_casing(val, 'upper')}")
        return "|".join(parts), errors

    errors.append("Invalid scope_mode.")
    return "", errors


def bucket_for_reset_policy(reset_policy: str, context: Dict[str, Any], now: datetime) -> Tuple[str, List[str]]:
    errors: List[str] = []
    ctx = _normalize_context(context)
    if reset_policy == "never":
        return "", errors
    if reset_policy == "yearly":
        return now.strftime("%Y"), errors
    if reset_policy == "monthly":
        return now.strftime("%Y-%m"), errors
    if reset_policy == "by_project":
        return _require_ctx_key(ctx, "project", errors, "project"), errors
    errors.append("Invalid reset_policy.")
    return "", errors


def compute_counter_key(scheme_id: str, scope_key: str, bucket: str) -> str:
    parts = [f"scheme:{scheme_id}", f"scope:{scope_key}"]
    if bucket:
        parts.append(f"bucket:{bucket}")
    return "|".join(parts)


def preview_number(
    scheme: NumberingScheme,
    context: Dict[str, Any],
    sequence_values: Any = None,
) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    scheme_dict = scheme_to_dict(scheme)
    seq_segments = _sequence_segments(scheme_dict.get("pattern_segments") or [])
    auto_seq_errors: List[str] = []
    auto_seq_index = _get_auto_sequence_index(scheme_dict, seq_segments, auto_seq_errors)
    errors.extend(auto_seq_errors)

    scope_key, scope_errors = build_scope_key(scheme_dict, context)
    errors.extend(scope_errors)
    if errors:
        return {}, errors

    seq_defaults = scheme_dict.get("seq") or {}
    reset_policy = str(seq_defaults.get("reset_policy") or DEFAULT_SEQ["reset_policy"])
    bucket, bucket_errors = bucket_for_reset_policy(reset_policy, context, datetime.utcnow())
    errors.extend(bucket_errors)
    if errors:
        return {}, errors

    resolved_sequence_values = _resolve_sequence_values(scheme_dict, sequence_values)
    counter_key = compute_counter_key(str(scheme.id), scope_key, bucket)
    if auto_seq_index >= 0:
        auto_start = resolved_sequence_values[auto_seq_index] if auto_seq_index < len(resolved_sequence_values) else _coerce_int(seq_defaults.get("start_at"), DEFAULT_SEQ["start_at"])
        next_value = peek_next_sequence(counter_key, auto_start)
        if auto_seq_index < len(resolved_sequence_values):
            resolved_sequence_values[auto_seq_index] = next_value

    candidate, cand_errors, _ = build_candidate_number(scheme_dict, context, resolved_sequence_values, datetime.utcnow())
    errors.extend(cand_errors)
    if errors:
        return {}, errors

    revision_policy = str((scheme_dict.get("revision") or {}).get("policy") or DEFAULT_REVISION["policy"])
    revision_start = str((scheme_dict.get("revision") or {}).get("start") or DEFAULT_REVISION["start"])
    revision = revision_for_new_part(revision_policy, revision_start)

    return {
        "candidate_part_number": candidate,
        "candidate_revision": revision,
        "display_code_candidate": build_display_code(candidate, revision),
        "scope_key_used": scope_key,
        "sequence_values_used": resolved_sequence_values,
        "auto_sequence_index": auto_seq_index,
    }, []


def allocate_number(
    scheme: NumberingScheme,
    context: Dict[str, Any],
    create_part_if_missing: bool,
    requested_revision_action: str,
    existing_part_number: str | None,
    user_email: str | None,
    cad_ref: Dict[str, Any] | None,
    sequence_values: Any = None,
) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    action = (requested_revision_action or "new_part").strip().lower()
    scheme_dict = scheme_to_dict(scheme)
    seq_segments = _sequence_segments(scheme_dict.get("pattern_segments") or [])
    auto_seq_errors: List[str] = []
    auto_seq_index = _get_auto_sequence_index(scheme_dict, seq_segments, auto_seq_errors)
    errors.extend(auto_seq_errors)

    if action in ("keep_existing", "revise_existing"):
        pn = (existing_part_number or context.get("part_number") or "").strip()
        if not pn:
            errors.append("existing_part_number is required for revision actions.")
            return {}, errors
        part = Part.objects(part_number=pn).order_by("-updated_at").first()
        if not part:
            errors.append("part not found.")
            return {}, errors
        if action == "keep_existing":
            return _format_allocation_result(part.part_number, part.revision, part.id, "", ""), []

        revision_policy = str((scheme_dict.get("revision") or {}).get("policy") or DEFAULT_REVISION["policy"])
        revision_start = str((scheme_dict.get("revision") or {}).get("start") or DEFAULT_REVISION["start"])
        new_rev = revision_for_existing(part.revision, revision_policy, revision_start)
        if Part.objects(part_number=pn, revision=new_rev).first():
            errors.append("revision already exists for part.")
            return {}, errors
        new_part = None
        if create_part_if_missing:
            new_part = _clone_part_with_revision(part, new_rev, cad_ref)
            new_part.save()
            _record_revision_history(new_part, user_email, "Revised via API")
        return _format_allocation_result(pn, new_rev, getattr(new_part, "id", None), "", ""), []

    scope_key, scope_errors = build_scope_key(scheme_dict, context)
    errors.extend(scope_errors)
    if errors:
        return {}, errors

    seq_defaults = scheme_dict.get("seq") or {}
    reset_policy = str(seq_defaults.get("reset_policy") or DEFAULT_SEQ["reset_policy"])
    bucket, bucket_errors = bucket_for_reset_policy(reset_policy, context, datetime.utcnow())
    errors.extend(bucket_errors)
    if errors:
        return {}, errors

    resolved_sequence_values = _resolve_sequence_values(scheme_dict, sequence_values)
    counter_key = compute_counter_key(str(scheme.id), scope_key, bucket)
    seq_value = None
    if auto_seq_index >= 0:
        auto_start = resolved_sequence_values[auto_seq_index] if auto_seq_index < len(resolved_sequence_values) else _coerce_int(seq_defaults.get("start_at"), DEFAULT_SEQ["start_at"])
        seq_value = consume_sequence(counter_key, auto_start)
        if auto_seq_index < len(resolved_sequence_values):
            resolved_sequence_values[auto_seq_index] = seq_value

    candidate, cand_errors, _ = build_candidate_number(scheme_dict, context, resolved_sequence_values, datetime.utcnow())
    errors.extend(cand_errors)
    if errors:
        return {}, errors

    revision_policy = str((scheme_dict.get("revision") or {}).get("policy") or DEFAULT_REVISION["policy"])
    revision_start = str((scheme_dict.get("revision") or {}).get("start") or DEFAULT_REVISION["start"])
    revision = revision_for_new_part(revision_policy, revision_start)

    if Part.objects(part_number=candidate, revision=revision).first():
        errors.append("part number already exists.")
        return {}, errors

    part_id = None
    if create_part_if_missing:
        attrs = {"revision": revision, "numbering_scheme_id": str(scheme.id)}
        if cad_ref:
            attrs["cad_ref"] = cad_ref
        part = Part(
            part_number=candidate,
            revision=revision,
            description="",
            uom="EA",
            attrs=attrs,
        )
        part.save()
        part_id = part.id
        _record_revision_history(part, user_email, "Allocated via API")

    return {
        "part_number": candidate,
        "revision": revision,
        "display_code": build_display_code(candidate, revision),
        "part_id": str(part_id) if part_id else None,
        "counter_key": counter_key,
        "next_value_after": seq_value + 1 if seq_value is not None else None,
        "scope_key_used": scope_key,
        "sequence_values_used": resolved_sequence_values,
        "auto_sequence_index": auto_seq_index,
    }, []


def revision_for_new_part(policy: str, start: str) -> str:
    policy = (policy or "").strip().lower()
    if policy == "none":
        return ""
    if policy == "numeric":
        return _normalize_numeric_revision(start or "01")
    return (start or "A").upper()


def revision_for_existing(current: str, policy: str, start: str) -> str:
    policy = (policy or "").strip().lower()
    if policy == "none":
        return ""
    if policy == "numeric":
        return _increment_numeric_revision(current, start)
    return _increment_alpha_revision(current, start)


def scheme_to_dict(scheme: NumberingScheme) -> Dict[str, Any]:
    return {
        "id": str(scheme.id),
        "name": scheme.name,
        "description": scheme.description or "",
        "is_active": bool(scheme.is_active),
        "is_preset": bool(getattr(scheme, "is_preset", False)),
        "is_recommended": bool(getattr(scheme, "is_recommended", False)),
        "visibility": getattr(scheme, "visibility", "advanced_only"),
        "pattern_segments": scheme.pattern_segments or [],
        "separator": scheme.separator or "-",
        "scope_mode": scheme.scope_mode or "global",
        "scope_keys": scheme.scope_keys or [],
        "seq": scheme.seq or {},
        "revision": scheme.revision or {},
        "validation_rules": scheme.validation_rules or {},
        "audit": scheme.audit or {},
    }


def peek_next_sequence(counter_key: str, start_at: int) -> int:
    counter = NumberingCounter.objects(counter_key=counter_key).first()
    if counter and counter.next_value:
        return max(int(counter.next_value), int(start_at))
    return max(int(start_at), 1)


def consume_sequence(counter_key: str, start_at: int) -> int:
    coll = NumberingCounter._get_collection()
    now = datetime.utcnow()
    start_at = max(int(start_at), 1)

    try:
        NumberingCounter(counter_key=counter_key, next_value=start_at + 1, updated_at=now).save()
        return start_at
    except NotUniqueError:
        pass

    doc = coll.find_one_and_update(
        {"counter_key": counter_key},
        {"$inc": {"next_value": 1}, "$set": {"updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if not doc or "next_value" not in doc:
        return start_at
    stored_next = int(doc["next_value"])
    allocated = stored_next - 1
    if allocated < start_at:
        coll.update_one(
            {"counter_key": counter_key},
            {"$set": {"next_value": start_at + 1, "updated_at": now}},
        )
        return start_at
    return allocated


def build_display_code(part_number: str, revision: str) -> str:
    if revision:
        return f"{part_number}-{revision}"
    return part_number


def _normalize_segments(raw_segments: Any, errors: List[str]) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    if not isinstance(raw_segments, list):
        errors.append("pattern_segments must be a list.")
        return segments
    for seg in raw_segments:
        if not isinstance(seg, dict):
            errors.append("pattern_segments entries must be objects.")
            continue
        kind = str(seg.get("kind") or "").strip().lower()
        entry: Dict[str, Any] = {"kind": kind}
        if kind == "literal":
            entry["value"] = str(seg.get("value") or "").strip()
        elif kind == "field":
            entry["field"] = str(seg.get("field") or "").strip()
            entry["casing"] = str(seg.get("casing") or "upper").strip().lower()
            if seg.get("pad_left") is not None:
                entry["pad_left"] = _coerce_int(seg.get("pad_left"), 0)
            if seg.get("pad_char") is not None:
                entry["pad_char"] = str(seg.get("pad_char") or "0")[:1]
        elif kind == "seq":
            if seg.get("padding") is not None:
                entry["padding"] = _coerce_int(seg.get("padding"), DEFAULT_SEQ["padding"])
            if seg.get("base") is not None:
                entry["base"] = _coerce_int(seg.get("base"), DEFAULT_SEQ["base"])
            if seg.get("start_at") is not None:
                entry["start_at"] = _coerce_int(seg.get("start_at"), DEFAULT_SEQ["start_at"])
            if "auto_counter" in seg:
                entry["auto_counter"] = _coerce_bool(seg.get("auto_counter"), False)
        elif kind == "date":
            entry["fmt"] = str(seg.get("fmt") or "").strip()
        segments.append(entry)
    return segments


def _sequence_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [seg for seg in segments if isinstance(seg, dict) and str(seg.get("kind") or "").lower().strip() == "seq"]


def _get_auto_sequence_index(scheme: Dict[str, Any], seq_segments: List[Dict[str, Any]], errors: List[str] | None = None) -> int:
    if not seq_segments:
        return -1

    automatic = [idx for idx, seg in enumerate(seq_segments) if _coerce_bool(seg.get("auto_counter"), False)]
    if len(seq_segments) == 1:
        if len(automatic) > 1 and errors is not None:
            errors.append("Only one seq segment can be automatic.")
        return automatic[0] if automatic else 0

    if len(automatic) != 1:
        if errors is not None:
            errors.append("Exactly one seq segment must be marked automatic when a scheme has multiple sequence segments.")
        return -1

    return automatic[0]


def _resolve_sequence_values(scheme: Dict[str, Any], raw_values: Any) -> List[int]:
    seq_defaults = scheme.get("seq") or {}
    fallback_start = _coerce_int(seq_defaults.get("start_at"), DEFAULT_SEQ["start_at"])
    seq_segments = _sequence_segments(scheme.get("pattern_segments") or [])
    auto_index = _get_auto_sequence_index(scheme, seq_segments)
    values: List[int] = []
    for index, seg in enumerate(seq_segments):
        if index == auto_index or (auto_index < 0 and len(seq_segments) == 1):
            values.append(max(1, fallback_start))
            continue
        values.append(max(1, _coerce_int(seg.get("start_at"), fallback_start)))
    if isinstance(raw_values, dict):
        for key, value in raw_values.items():
            try:
                index = int(key)
            except Exception:
                continue
            if 0 <= index < len(values):
                values[index] = max(1, _coerce_int(value, values[index]))
    elif isinstance(raw_values, (list, tuple)):
        for index, value in enumerate(raw_values):
            if index >= len(values):
                break
            values[index] = max(1, _coerce_int(value, values[index]))
    return values


def _example_context_from_scheme(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    defaults = {
        "type": "TYPE",
        "family": "FAM",
        "subfamily": "SUB",
        "project": "PROJ",
        "site": "SITE",
    }
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        if str(seg.get("kind") or "").lower() == "field":
            key = str(seg.get("field") or "").strip().lower()
            if key and key not in defaults:
                defaults[key] = key.upper()
    return defaults


def _normalize_context(context: Dict[str, Any] | None) -> Dict[str, str]:
    ctx: Dict[str, str] = {}
    for k, v in (context or {}).items():
        key = str(k).strip().lower()
        if not key:
            continue
        val = str(v).strip()
        if val:
            ctx[key] = val
    return ctx


def _apply_casing(value: str, casing: str) -> str:
    if casing == "lower":
        return value.lower()
    if casing == "none":
        return value
    return value.upper()


def _format_sequence(value: int, padding: int, base: int) -> str:
    if base == 36:
        encoded = _to_base36(value)
    else:
        encoded = str(int(value))
    if padding > 0:
        return encoded.rjust(padding, "0")
    return encoded


def _format_date(now: datetime, fmt: str) -> str:
    if fmt == "YYYY":
        return now.strftime("%Y")
    if fmt == "YY":
        return now.strftime("%y")
    if fmt == "MM":
        return now.strftime("%m")
    if fmt == "YYYYMM":
        return now.strftime("%Y%m")
    return ""


def _to_base36(value: int) -> str:
    value = int(value)
    if value <= 0:
        return "0"
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    out = ""
    while value > 0:
        value, rem = divmod(value, 36)
        out = alphabet[rem] + out
    return out


def _allowed_charset_regex(allowed: str) -> re.Pattern | None:
    try:
        return re.compile(rf"^[{allowed}]+$")
    except re.error:
        return re.compile(r"^[A-Z0-9-]+$")


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _coerce_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.strip().lower() in ("true", "1", "yes", "y"):
            return True
        if value.strip().lower() in ("false", "0", "no", "n"):
            return False
    return fallback


def _require_ctx_key(ctx: Dict[str, str], key: str, errors: List[str], label: str) -> str:
    val = ctx.get(key, "")
    if not val:
        errors.append(f"context missing field '{label}'.")
        return ""
    return _apply_casing(val, "upper")


def _increment_alpha_revision(current: str, start: str) -> str:
    cur = (current or "").strip().upper()
    if not cur:
        return (start or "A").strip().upper()
    return _alpha_from_number(_alpha_to_number(cur) + 1)


def _alpha_to_number(value: str) -> int:
    out = 0
    for ch in value:
        if "A" <= ch <= "Z":
            out = out * 26 + (ord(ch) - 64)
    return out


def _alpha_from_number(value: int) -> str:
    if value <= 0:
        return "A"
    out = ""
    while value > 0:
        value, rem = divmod(value - 1, 26)
        out = chr(65 + rem) + out
    return out


def _normalize_numeric_revision(start: str) -> str:
    digits = "".join(ch for ch in start if ch.isdigit())
    if not digits:
        return "01"
    width = len(digits)
    return str(int(digits)).zfill(width)


def _increment_numeric_revision(current: str, start: str) -> str:
    width = len("".join(ch for ch in start if ch.isdigit())) or 2
    cur_digits = "".join(ch for ch in (current or "") if ch.isdigit())
    if not cur_digits:
        cur_digits = "".join(ch for ch in start if ch.isdigit()) or "0"
    next_val = int(cur_digits) + 1
    return str(next_val).zfill(width)


def _clone_part_with_revision(part: Part, revision: str, cad_ref: Dict[str, Any] | None) -> Part:
    attrs = dict(getattr(part, "attrs", {}) or {})
    attrs["revision"] = revision
    if cad_ref:
        attrs["cad_ref"] = cad_ref
    return Part(
        part_number=part.part_number,
        revision=revision,
        description=part.description or "",
        processes=list(part.processes or []),
        category=part.category or "",
        uom=part.uom or "EA",
        manufacturer=part.manufacturer or "",
        mfr_part=part.mfr_part or "",
        status=part.status or "active",
        docs=list(part.docs or []),
        attrs=attrs,
    )


def _record_revision_history(part: Part, user_email: str | None, note: str) -> None:
    PartRevisionHistory(
        part_id=part,
        part_number=part.part_number,
        revision=part.revision or "",
        status="WIP",
        change_note=note or "",
        created_by=user_email or "",
    ).save()


def _format_allocation_result(part_number: str, revision: str, part_id: Any, counter_key: str, scope_key: str) -> Dict[str, Any]:
    return {
        "part_number": part_number,
        "revision": revision or "",
        "display_code": build_display_code(part_number, revision or ""),
        "part_id": str(part_id) if part_id else None,
        "counter_key": counter_key or "",
        "next_value_after": None,
        "scope_key_used": scope_key or "",
    }
