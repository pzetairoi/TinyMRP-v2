from __future__ import annotations

import csv
import io
import math
import os
from typing import Any, Callable, Dict, Iterable, Optional, Sequence

from app.models.artifact import PartFile
from app.models.bom import BOMLink
from app.models.part import Part
from app.services.attrs import harvest_part_attrs
from app.services.canonical_fields import canonical_processes_for_part
from app.services.field_config import (
    context_field_ids,
    default_arena_header_for_field,
    field_index,
    get_field_config,
    resolve_part_field_values,
)
from app.services.part_norm import clean_rev

import re
from flask import current_app, has_app_context
from app.services.insights import HARDWARE_TERMS, normalized_processes as normalized_process_list


_ARENA_BOM_RESERVED_FIELD_IDS = {"thumbnail", "part_number", "description", "qty", "level"}
_ARENA_LINK_SUPPORTED_GROUPS = {"pdf", "dxf", "step"}
_ARENA_LINK_PRIORITY = {
    ("pdf", "pdf"): 0,
    ("dxf", "dxf"): 0,
    ("step", "step"): 0,
    ("step", "stp"): 1,
}
_ARENA_LINK_FOLDERS = {
    "pdf": "PDF",
    "dxf": "DXF",
    "step": "STEP",
}


def _clean_rev(value: Any) -> str:
    return clean_rev(value)


def _part_by(pn: str, rev: Optional[str]) -> Optional[Part]:
    if rev is None:
        return Part.objects(part_number__iexact=pn).order_by("-updated_at").first()
    return Part.objects(part_number__iexact=pn, revision__iexact=_clean_rev(rev)).first()


def _root_part_or_raise(root_pn: str, root_rev: Optional[str]) -> tuple[Part, str]:
    part = _part_by(root_pn, root_rev)
    if not part:
        raise RuntimeError("Part not found.")
    attrs = harvest_part_attrs(part)
    effective_rev = _clean_rev(attrs.get("revision") or part.revision or "")
    return part, effective_rev


def _child_links(parent_pn: str, parent_rev: Optional[str]) -> list[BOMLink]:
    rev_clean = _clean_rev(parent_rev)
    query = BOMLink.objects(parent_pn=parent_pn)
    if parent_rev is not None and "parent_rev" in BOMLink._fields:
        query = query.filter(parent_rev=rev_clean)
    return list(query.order_by("child_pn", "child_rev"))


def _csv_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        rounded = round(value, 1)
        return str(int(rounded)) if rounded.is_integer() else f"{rounded:.1f}"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_csv_text(item) for item in value if item is not None)
    return str(value)


def _quantity_text(value: Any) -> str:
    """Format BOM quantities without the general one-decimal display rounding."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _csv_text(value)
    if not math.isfinite(number):
        return str(number)
    return format(number, ".15g")


def _desc_from(pn: str, rev: str) -> str:
    safe_rev = str(rev or "").replace("/", "-").replace("\\", "-").replace(":", "-")
    return f"{pn}_REV_{safe_rev}"


def _join_base_url(base_url: str, leaf: str) -> str:
    base = str(base_url or "").strip()
    if not base:
        return leaf
    if base.endswith(("/", "=", "?", "&")):
        return f"{base}{leaf}"
    return f"{base}/{leaf}"


def _resolve_values(
    part: Optional[Part],
    field_ids: Sequence[str],
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    attrs = harvest_part_attrs(part) if part else {}
    return resolve_part_field_values(
        part,
        field_ids,
        attrs=attrs,
        config=get_field_config(),
        extra=extra,
        coverage=None,
    )


def _field_ids_for_arena_bom(requested_ids: Sequence[str] | None) -> list[str]:
    config = get_field_config()
    available = field_index(config)
    source = list(requested_ids or context_field_ids("arena_bom", config, default=True))
    out: list[str] = []
    seen = set()
    for field_id in source:
        normalized = str(field_id or "").strip()
        if not normalized or normalized in seen or normalized not in available:
            continue
        if normalized in _ARENA_BOM_RESERVED_FIELD_IDS:
            continue
        if available[normalized].get("data_type") == "image":
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _field_header(field_id: str, field_def: dict[str, Any]) -> str:
    header = str(field_def.get("arena_header") or "").strip()
    if header:
        return header
    return default_arena_header_for_field(field_id, str(field_def.get("label") or "").strip())


def _write_csv(rows: Iterable[dict[str, Any]], headers: Sequence[str]) -> bytes:
    sio = io.StringIO(newline="")
    writer = csv.DictWriter(sio, fieldnames=list(headers), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_text(row.get(key)) for key in headers})
    return sio.getvalue().encode("utf-8-sig")


def build_arena_bom_csv(
    root_pn: str,
    root_rev: Optional[str],
    *,
    field_ids: Sequence[str] | None = None,
    is_allowed: Optional[Callable[[str, str], bool]] = None,
) -> tuple[str, bytes]:
    root_part, root_effective_rev = _root_part_or_raise(root_pn, root_rev)
    config = get_field_config()
    fields_by_id = field_index(config)
    selected_field_ids = _field_ids_for_arena_bom(field_ids)

    extra_headers: list[str] = []
    header_by_field_id: dict[str, str] = {}
    used_headers = {"item number", "line number", "level", "quantity", "item name", "description"}
    for field_id in selected_field_ids:
        field = fields_by_id.get(field_id)
        if not field:
            continue
        header = _field_header(field_id, field)
        header_key = header.strip().lower()
        if not header or header_key in used_headers:
            continue
        used_headers.add(header_key)
        extra_headers.append(header)
        header_by_field_id[field_id] = header

    headers = ["item number", "line number", "level", "quantity", "item name", "description", *extra_headers]
    rows: list[dict[str, Any]] = []

    def values_for(
        part: Optional[Part],
        *,
        pn: str,
        rev: str,
        description: str,
        level: int,
        quantity: float,
        total_qty: float,
    ) -> Dict[str, Any]:
        values = _resolve_values(
            part,
            selected_field_ids,
            extra={
                "part_number": pn,
                "revision": rev,
                "description": description,
                "qty": quantity,
                "level": level,
                "level_qty": quantity,
                "total_qty": total_qty,
            },
        )
        out: Dict[str, Any] = {}
        for field_id, header in header_by_field_id.items():
            value = values.get(field_id, "")
            out[header] = _quantity_text(value) if field_id in {"level_qty", "total_qty"} else value
        return out

    root_values = values_for(
        root_part,
        pn=root_part.part_number,
        rev=root_effective_rev,
        description=_csv_text(_resolve_values(root_part, ["description"], extra={"part_number": root_part.part_number, "revision": root_effective_rev}).get("description")),
        level=0,
        quantity=1.0,
        total_qty=1.0,
    )
    root_description = _resolve_values(
        root_part,
        ["description"],
        extra={"part_number": root_part.part_number, "revision": root_effective_rev},
    ).get("description", "")
    rows.append(
        {
            "item number": root_part.part_number,
            "line number": 3,
            "level": 0,
            "quantity": 1,
            "item name": root_description,
            "description": root_description,
            **root_values,
        }
    )

    def walk(parent_pn: str, parent_rev: str, depth: int, ancestry: tuple[tuple[str, str], ...], parent_total_qty: float) -> None:
        for link in _child_links(parent_pn, parent_rev):
            child_pn = str(getattr(link, "child_pn", None) or "").strip()
            if not child_pn:
                continue
            child_rev = _clean_rev(getattr(link, "child_rev", "") or "")
            child_key = (child_pn, child_rev)
            if child_key in ancestry:
                continue
            if is_allowed and not is_allowed(child_pn, child_rev):
                raise RuntimeError("Export scope is incomplete.")
            child_part = _part_by(child_pn, child_rev)
            child_attrs = harvest_part_attrs(child_part) if child_part else {}
            effective_rev = _clean_rev(child_attrs.get("revision") or (child_part.revision if child_part else "") or child_rev)
            description = _csv_text(
                _resolve_values(child_part, ["description"], extra={"part_number": child_pn, "revision": effective_rev}).get("description")
            )
            next_ancestry = ancestry + (child_key,)
            # BOMLink.qty is the authoritative quantity for this parent/child
            # relationship. ``occurrences`` only preserves the individual
            # source rows that were aggregated during import; exporting those
            # as separate Arena BOM lines duplicates both the item and any
            # descendant subtree.
            quantity = float(getattr(link, "qty", 1.0) or 0.0)
            total_qty = float(parent_total_qty or 0.0) * quantity
            row = {
                "item number": child_pn,
                "line number": 3,
                "level": depth,
                "quantity": _quantity_text(quantity),
                "item name": description,
                "description": description,
            }
            row.update(
                values_for(
                    child_part,
                    pn=child_pn,
                    rev=effective_rev,
                    description=description,
                    level=depth,
                    quantity=quantity,
                    total_qty=total_qty,
                )
            )
            rows.append(row)
            walk(child_pn, effective_rev, depth + 1, next_ancestry, total_qty)

    walk(root_part.part_number, root_effective_rev, 1, ((root_part.part_number, root_effective_rev),), 1.0)

    filename = f"{root_part.part_number}_{root_effective_rev or 'no_rev'}_arena_bom.csv"
    return filename, _write_csv(rows, headers)


def _collect_unique_parts(
    root_pn: str,
    root_rev: str,
    *,
    is_allowed: Optional[Callable[[str, str], bool]] = None,
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen = set()

    def add(pn: str, rev: str) -> None:
        key = (pn, _clean_rev(rev))
        if key in seen:
            return
        seen.add(key)
        out.append(key)

    def walk(parent_pn: str, parent_rev: str, ancestry: tuple[tuple[str, str], ...]) -> None:
        add(parent_pn, parent_rev)
        for link in _child_links(parent_pn, parent_rev):
            child_pn = str(getattr(link, "child_pn", None) or "").strip()
            if not child_pn:
                continue
            child_rev = _clean_rev(getattr(link, "child_rev", "") or "")
            child_key = (child_pn, child_rev)
            if child_key in ancestry:
                continue
            if is_allowed and not is_allowed(child_pn, child_rev):
                raise RuntimeError("Export scope is incomplete.")
            walk(child_pn, child_rev, ancestry + (child_key,))

    if not is_allowed or is_allowed(root_pn, root_rev):
        walk(root_pn, root_rev, ((root_pn, root_rev),))
    return out


def _best_file_candidates(pn: str, rev: str) -> dict[str, PartFile]:
    best: dict[str, tuple[int, PartFile]] = {}
    for row in PartFile.objects(part_number__iexact=pn, revision__iexact=rev).only("ext_group", "ext", "rel_path", "path"):
        ext_group = str(getattr(row, "ext_group", "") or "").strip().lower()
        ext = str(getattr(row, "ext", "") or "").strip().lower()
        if ext_group not in _ARENA_LINK_SUPPORTED_GROUPS:
            continue
        if (ext_group, ext) not in _ARENA_LINK_PRIORITY:
            continue
        score = _ARENA_LINK_PRIORITY[(ext_group, ext)]
        current = best.get(ext_group)
        if current is None or score < current[0]:
            best[ext_group] = (score, row)
    return {group: item[1] for group, item in best.items()}


def build_arena_file_links_csv(
    root_pn: str,
    root_rev: Optional[str],
    *,
    base_url: str,
    author: str = "",
    is_allowed: Optional[Callable[[str, str], bool]] = None,
) -> tuple[str, bytes]:
    if not str(base_url or "").strip():
        raise RuntimeError("BASE URL is required.")
    root_part, root_effective_rev = _root_part_or_raise(root_pn, root_rev)
    parts = _collect_unique_parts(root_part.part_number, root_effective_rev, is_allowed=is_allowed)

    headers = [
        "item number",
        "file title",
        "file number",
        "edition identifier",
        "file category",
        "file category path",
        "file location",
        "file format",
        "author",
        "file description",
        "file active",
    ]
    rows: list[dict[str, Any]] = []
    for pn, rev in parts:
        part_doc = _part_by(pn, rev)
        if _is_hardware_or_fastener(part_doc):
            continue
        best_files = _best_file_candidates(pn, rev)
        if not best_files:
            continue
        desc = _desc_from(pn, rev)
        for group in ("pdf", "dxf", "step"):
            pf = best_files.get(group)
            if not pf:
                continue
            file_title = os.path.basename(pf.rel_path or pf.path or "") or f"{desc}.{group}"
            file_format = "step" if group == "step" else group
            rows.append(
                {
                    "item number": pn,
                    "file title": file_title,
                    "file number": "",
                    "edition identifier": _edition_identifier(rev),
                    "file category": "Drawing" if file_format == "pdf" else "CAD File",
                    "file category path": "",
                    "file location": _join_base_url(base_url, f"{_ARENA_LINK_FOLDERS[file_format]}/{desc}.{file_format}"),
                    "file format": file_format,
                    "author": author,
                    "file description": desc,
                    "file active": 1 if file_format == "pdf" else 0,
                }
            )

    filename = f"{root_part.part_number}_{root_effective_rev or 'no_rev'}_arena_file_links.csv"
    return filename, _write_csv(rows, headers)


def _edition_identifier(rev: Any) -> str:
    return _clean_rev(rev) or "1"

def _desc_from(pn: str, rev: str) -> str:
    safe_rev = _edition_identifier(rev).replace("/", "-").replace("\\", "-").replace(":", "-")
    return f"{pn}_REV_{safe_rev}"


def _raw_process_terms(part: Optional[Part], attrs: dict[str, Any]) -> set[str]:
    values: list[Any] = []
    if part is not None:
        values.extend(canonical_processes_for_part(part))

    for key in ("process", "process2", "process3", "processes"):
        raw = attrs.get(key)
        if isinstance(raw, (list, tuple, set)):
            values.extend(raw)
        elif raw is not None:
            values.append(raw)

    terms: set[str] = set()
    for value in values:
        for token in re.split(r"\s*(?:,|;|/|\||&|\+|\r|\n)\s*", str(value or "").lower()):
            token = token.strip()
            if token:
                terms.add(token)
    return terms


def _is_hardware_or_fastener(part: Optional[Part]) -> bool:
    if not part:
        return False

    attrs = harvest_part_attrs(part)
    meta = current_app.config.get("PROCESS_META", {}) if has_app_context() else {}

    normalized = set(
        normalized_process_list(
            attrs,
            list(getattr(part, "processes", []) or []),
            meta,
        )
        or []
    )
    raw_terms = _raw_process_terms(part, attrs)

    return bool((normalized | raw_terms) & HARDWARE_TERMS)
