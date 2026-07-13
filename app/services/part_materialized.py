from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from app.models.artifact import PartFile
from app.models.part import Part
from app.services.attrs import harvest_part_attrs
from app.services.canonical_fields import sync_part_canonical_fields
from app.services.field_config import get_field_config, materialized_field_ids, resolve_part_field_values
from app.services.filescan import datasheet_attr_present
from app.services.part_annotations import annotation_payload
from app.services.part_norm import clean_rev


FILE_GROUP_FLAG_FIELDS: Dict[str, str] = {
    "pdf": "has_pdf",
    "png": "has_png",
    "dxf": "has_dxf",
    "step": "has_step",
    "edr": "has_edr",
    "3mf": "has_3mf",
    "ply": "has_ply",
    "stl": "has_stl",
    "datasheet": "has_datasheet",
}


def normalized_part_revision(part: Part, attrs: Optional[Dict[str, Any]] = None) -> str:
    attrs = attrs or {}
    return clean_rev(attrs.get("revision") or getattr(part, "revision", "") or "")


def _pair_key(pn: str, rev: str) -> tuple[str, str]:
    return (str(pn or "").strip().lower(), clean_rev(rev).lower())


def batch_file_groups_for_parts(parts: Iterable[Part]) -> dict[tuple[str, str], set[str]]:
    part_list = [part for part in parts if getattr(part, "part_number", None)]
    if not part_list:
        return {}

    target_pairs: dict[tuple[str, str], tuple[str, str]] = {}
    for part in part_list:
        attrs = harvest_part_attrs(part)
        rev = normalized_part_revision(part, attrs)
        target_pairs[_pair_key(part.part_number, rev)] = (part.part_number, rev)

    groups_by_pair: dict[tuple[str, str], set[str]] = {}
    pn_list = sorted({part.part_number for part in part_list if part.part_number})
    for row in PartFile.objects(part_number__in=pn_list).only("part_number", "revision", "ext_group"):
        group = str(getattr(row, "ext_group", "") or "").strip().lower()
        if not group:
            continue
        match = target_pairs.get(_pair_key(getattr(row, "part_number", ""), getattr(row, "revision", "") or ""))
        if not match:
            continue
        groups_by_pair.setdefault(match, set()).add(group)

    for part in part_list:
        attrs = harvest_part_attrs(part)
        rev = normalized_part_revision(part, attrs)
        key = (part.part_number, rev)
        if datasheet_attr_present(attrs):
            groups_by_pair.setdefault(key, set()).add("datasheet")
        else:
            groups_by_pair.setdefault(key, set())

    return groups_by_pair


def file_groups_for_part(part: Part, *, attrs: Optional[Dict[str, Any]] = None) -> set[str]:
    attrs = attrs or harvest_part_attrs(part)
    rev = normalized_part_revision(part, attrs)
    groups: set[str] = set()
    for row in PartFile.objects(part_number__iexact=part.part_number, revision__iexact=rev).only("ext_group"):
        group = str(getattr(row, "ext_group", "") or "").strip().lower()
        if group:
            groups.add(group)
    if datasheet_attr_present(attrs):
        groups.add("datasheet")
    return groups


def _apply_file_coverage_fields(part: Part, groups: set[str]) -> bool:
    changed = False
    normalized_groups = sorted({str(group or "").strip().lower() for group in groups if str(group or "").strip()})
    if list(getattr(part, "file_groups", []) or []) != normalized_groups:
        part.file_groups = normalized_groups
        changed = True

    for group, flag_field in FILE_GROUP_FLAG_FIELDS.items():
        expected = group in groups
        if bool(getattr(part, flag_field, False)) != expected:
            setattr(part, flag_field, expected)
            changed = True
    return changed


def _apply_annotation_search_fields(part: Part, attrs: Optional[Dict[str, Any]] = None) -> bool:
    payload = annotation_payload(part, attrs=attrs)
    changed = False
    notes_search = str(payload.get("notes") or "")
    comments_search = str(payload.get("comments_search") or "")
    if getattr(part, "notes_search", "") != notes_search:
        part.notes_search = notes_search
        changed = True
    if getattr(part, "comments_search", "") != comments_search:
        part.comments_search = comments_search
        changed = True
    return changed


def _apply_materialized_field_values(
    part: Part,
    config: dict[str, Any],
    attrs: dict[str, Any],
    groups: set[str],
) -> bool:
    field_ids = materialized_field_ids(config)
    next_values: dict[str, Any] = {}
    if field_ids:
        next_values = resolve_part_field_values(
            part,
            field_ids,
            attrs=attrs,
            config=config,
            extra={
                "part_number": part.part_number,
                "revision": normalized_part_revision(part, attrs),
            },
            coverage=groups,
        )
    if dict(getattr(part, "field_values", {}) or {}) != next_values:
        part.field_values = next_values
        return True
    return False


def sync_part_materialized_fields(
    part: Part,
    *,
    config: Optional[dict[str, Any]] = None,
    attrs: Optional[dict[str, Any]] = None,
    coverage: Optional[set[str]] = None,
) -> bool:
    if not part:
        return False

    config = config or get_field_config()
    raw_attrs = dict(getattr(part, "attrs", {}) or {})
    before_canonical = dict(getattr(part, "canonical", {}) or {})
    before_processes = list(getattr(part, "processes", None) or [])
    before_top_level = {
        field: getattr(part, field, None)
        for field in ("description", "revision", "category", "uom", "manufacturer", "mfr_part")
    }
    process_override = None
    try:
        from app.services.import_zip import _is_hardware_by_folder, _is_hardware_by_process

        if _is_hardware_by_folder(raw_attrs) or _is_hardware_by_process(raw_attrs):
            process_override = ["hardware"]
    except Exception:
        process_override = None
    sync_part_canonical_fields(part, raw_attrs=raw_attrs, process_override=process_override)
    attrs = harvest_part_attrs(part) if attrs is None else attrs
    groups = set(coverage) if coverage is not None else file_groups_for_part(part, attrs=attrs)

    changed = (
        before_canonical != dict(getattr(part, "canonical", {}) or {})
        or before_processes != list(getattr(part, "processes", None) or [])
        or before_top_level
        != {
            field: getattr(part, field, None)
            for field in ("description", "revision", "category", "uom", "manufacturer", "mfr_part")
        }
    )
    if _apply_annotation_search_fields(part, attrs=attrs):
        changed = True
    if _apply_file_coverage_fields(part, groups):
        changed = True
    if _apply_materialized_field_values(part, config, attrs, groups):
        changed = True
    return changed


def sync_materialized_fields_for_pairs(
    pairs: Iterable[tuple[str, str]],
    *,
    config: Optional[dict[str, Any]] = None,
) -> dict[str, int]:
    config = config or get_field_config()
    scanned = 0
    updated = 0
    seen: set[tuple[str, str]] = set()
    for pn, rev in pairs:
        pn_clean = str(pn or "").strip()
        rev_clean = clean_rev(rev)
        if not pn_clean or (pn_clean.lower(), rev_clean.lower()) in seen:
            continue
        seen.add((pn_clean.lower(), rev_clean.lower()))
        part = Part.objects(part_number__iexact=pn_clean, revision__iexact=rev_clean).first()
        if not part and rev_clean:
            for candidate in Part.objects(part_number__iexact=pn_clean).only("part_number", "revision", "attrs", "canonical"):
                attrs = harvest_part_attrs(candidate)
                if normalized_part_revision(candidate, attrs).lower() == rev_clean.lower():
                    part = candidate
                    break
        if not part:
            continue
        scanned += 1
        if sync_part_materialized_fields(part, config=config):
            part.save(sync_materialized=False)
            updated += 1
    return {"scanned": scanned, "updated": updated}


def rebuild_part_materialized_fields(*, config: Optional[dict[str, Any]] = None) -> dict[str, int]:
    config = config or get_field_config()
    report = {"scanned": 0, "updated": 0, "errors": 0}
    parts = list(Part.objects())
    coverage_by_pair = batch_file_groups_for_parts(parts)

    for part in parts:
        report["scanned"] += 1
        try:
            attrs = harvest_part_attrs(part)
            rev = normalized_part_revision(part, attrs)
            coverage = coverage_by_pair.get((part.part_number, rev), set())
            if sync_part_materialized_fields(part, config=config, attrs=attrs, coverage=coverage):
                part.save(sync_materialized=False)
                report["updated"] += 1
        except Exception:
            report["errors"] += 1
    return report
