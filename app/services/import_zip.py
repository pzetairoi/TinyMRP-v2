from __future__ import annotations
import ast
import json
import math
import re
from collections import defaultdict
from typing import Any, Iterable
from flask import current_app, has_app_context
from app.services.part_norm import clean_pn, clean_qty, clean_rev
from app.services.processmeta import normalize_processes
DEFAULT_OVERRIDE_MODE = "unless_existing_approved"
_OVERRIDE_ALIASES = {
    "default": DEFAULT_OVERRIDE_MODE,
    "override_unless_existing_approved": DEFAULT_OVERRIDE_MODE,
    "override_unless_approved": DEFAULT_OVERRIDE_MODE,
}
_OVERRIDE_MODES = {
    DEFAULT_OVERRIDE_MODE,
    "preserve",
    "approved_only",
    "always",
}
def normalize_override_mode(value: object) -> str:
    mode = str(value or DEFAULT_OVERRIDE_MODE).strip().lower()
    mode = _OVERRIDE_ALIASES.get(mode, mode)
    return mode if mode in _OVERRIDE_MODES else DEFAULT_OVERRIDE_MODE
def _base_pn(value: object) -> str:
    return clean_pn(str(value or "").split("^", 1)[0])
def _issue(
    report: dict[str, Any] | None,
    severity: str,
    stage: str,
    message: str,
    **context: Any,
) -> None:
    if report is None:
        return
    row = {"severity": severity, "stage": stage, "message": message}
    row.update({key: value for key, value in context.items() if value not in (None, "")})
    report.setdefault("errors" if severity == "error" else "warnings", []).append(row)
def _increment(report: dict[str, Any] | None, key: str, amount: int = 1) -> None:
    if report is not None:
        report[key] = int(report.get(key) or 0) + amount
def _parse_flatbom(
    text: str,
    source_name: str = "",
    max_warnings: int = 3,
    report: dict[str, Any] | None = None,
) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    failures = 0
    for line_number, raw in enumerate((text or "").lstrip("\ufeff").splitlines(), 1):
        line = raw.strip().lstrip("\ufeff")
        if not line:
            continue
        try:
            try:
                value = json.loads(line.replace("...", ""))
            except (ValueError, TypeError):
                value = ast.literal_eval(line.replace("...", ""))
        except Exception as exc:
            failures += 1
            _increment(report, "flat_lines_failed_parse")
            if failures <= max_warnings:
                current_app.logger.warning(
                    "FLATBOM parse failed (%s) line=%s: %s",
                    source_name or "FLATBOM",
                    line_number,
                    line[:160].replace("\t", " "),
                )
            _issue(
                report,
                "error",
                "flatbom.parse",
                "Failed to parse FLATBOM line.",
                file=source_name,
                line_number=line_number,
                exception_type=type(exc).__name__,
            )
            continue
        if not isinstance(value, dict):
            _increment(report, "flat_lines_skipped_not_dict")
            _issue(
                report,
                "warning",
                "flatbom.parse",
                "FLATBOM line did not evaluate to a dict (skipped).",
                file=source_name,
                line_number=line_number,
            )
            continue
        clean = {
            str(key).strip(): item.strip() if isinstance(item, str) else item
            for key, item in value.items()
            if key is not None and str(key).strip()
        }
        rows.append((line_number, clean))
    return rows
def _attr_ci_value(attrs: dict[str, Any], key: str) -> list[str]:
    return [
        str(item)
        for raw_key, value in (attrs or {}).items()
        if str(raw_key).strip().casefold() == key.casefold() and value is not None
        for item in (value if isinstance(value, (list, tuple)) else [value])
    ]
def _hardware_folder_tokens() -> list[str]:
    configured = current_app.config.get("HARDWARE_FOLDERS") or [] if has_app_context() else []
    values = re.split(r"[;,]", configured) if isinstance(configured, str) else configured
    tokens: list[str] = []
    for value in values:
        for chunk in re.split(r"[^A-Za-z0-9]+", str(value or "").casefold()):
            if chunk:
                tokens.extend(
                    candidate
                    for candidate in (
                        chunk,
                        chunk[:-3] + "y" if chunk.endswith("ies") else "",
                        chunk[:-2] if chunk.endswith("es") else "",
                        chunk[:-1] if chunk.endswith("s") else "",
                    )
                    if candidate
                )
    return list(dict.fromkeys(tokens))
def _is_hardware_by_folder(attrs: dict[str, Any]) -> bool:
    path = " ".join(
        value
        for key in ("folder", "file", "filepath", "path", "nativepath", "native_file", "file_path")
        for value in _attr_ci_value(attrs, key)
    ).casefold()
    words = re.split(r"[^a-z0-9]+", path)
    return any(token in path or any(token in word for word in words) for token in _hardware_folder_tokens())
def _is_hardware_by_process(attrs: dict[str, Any]) -> bool:
    return "hardware" in normalize_processes(
        attrs or {},
        current_app.config.get("PROCESS_META", {}) or {} if has_app_context() else {},
    )
def _normalize_part(row: dict[str, Any]) -> dict[str, Any]:
    lower = {str(key).strip().casefold(): value for key, value in row.items()}
    description = str(lower.get("description") or "")
    for key in ("desc1", "desc2", "desc3", "desc"):
        if lower.get(key):
            description = f"{description} {lower[key]}".strip()
    return {
        "part_number": _base_pn(
            lower.get("partnumber") or lower.get("part_number") or lower.get("pn")
        ),
        "revision": clean_rev(lower.get("revision") or lower.get("rev") or ""),
        "description": description.strip(),
        "category": str(lower.get("category") or "").strip(),
        "uom": str(lower.get("uom") or "EA").strip() or "EA",
        "attrs": dict(row),
    }
def _item_seq(item_number: str) -> object:
    value = str(item_number or "").split(".")[-1].strip()
    try:
        return int(value)
    except (TypeError, ValueError):
        return value
def _definition(
    links: Iterable[tuple[str, str, str, str, float, object]],
) -> dict[tuple[str, str], float]:
    totals: dict[tuple[str, str], float] = defaultdict(float)
    for _ppn, _prev, cpn, crev, qty, _seq in links:
        totals[(_base_pn(cpn), clean_rev(crev))] += float(qty or 0)
    return dict(totals)
def _same_definition(
    left: dict[tuple[str, str], float],
    right: dict[tuple[str, str], float],
) -> bool:
    return set(left) == set(right) and all(
        math.isclose(left[key], right[key], rel_tol=1e-9, abs_tol=1e-9)
        for key in left
    )
def _parse_treebom(
    text: str,
    source_name: str = "",
    report: dict[str, Any] | None = None,
) -> list[tuple[str, str, str, str, float, object]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate((text or "").splitlines(), 1):
        columns = line.split("\t")
        if len(columns) < 4 or columns[0].strip() == "ITEM NO.":
            continue
        item_number = columns[0].strip()
        part_number = _base_pn(columns[1])
        if not part_number:
            _increment(report, "rows_skipped_blank_part")
            _issue(
                report,
                "warning",
                "treebom.parse",
                f"TREEBOM row skipped: blank PART NUMBER (item={item_number}).",
                file=source_name,
                line_number=line_number,
            )
            continue
        try:
            quantity = float(columns[3].strip() or 1)
        except ValueError:
            _increment(report, "tree_rows_failed_qty")
            _issue(
                report,
                "error",
                "treebom.parse",
                f"TREEBOM row skipped: failed to parse QTY (item={item_number}).",
                file=source_name,
                line_number=line_number,
                part_number=part_number,
            )
            continue
        rows.append(
            {
                "item": item_number,
                "pn": part_number,
                "rev": clean_rev(columns[2]),
                "qty": quantity,
                "line": line_number,
            }
        )
    by_item = {row["item"]: (row["pn"], row["rev"]) for row in rows}
    occurrences: dict[
        tuple[str, str],
        dict[str, list[tuple[str, str, str, str, float, object]]],
    ] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        item = row["item"]
        if item == "1":
            continue
        parent_item = item.rsplit(".", 1)[0] if "." in item else ""
        while parent_item and parent_item not in by_item:
            parent_item = parent_item.rsplit(".", 1)[0] if "." in parent_item else ""
        if not parent_item:
            continue
        parent = by_item[parent_item]
        child = (row["pn"], row["rev"])
        if parent == child:
            _issue(
                report,
                "error",
                "treebom.integrity",
                f"BOM self-reference blocked at tree path {item}.",
                file=source_name,
                line_number=row["line"],
                part_number=child[0],
            )
            if report is not None:
                report["bom_integrity_status"] = "conflict"
            continue
        occurrences[parent][parent_item].append(
            (*parent, *child, clean_qty(row["qty"]), _item_seq(item))
        )
    output: list[tuple[str, str, str, str, float, object]] = []
    for parent, copies in occurrences.items():
        values = list(copies.items())
        first_path, first_links = values[0]
        conflicts = [
            path
            for path, links in values[1:]
            if not _same_definition(_definition(first_links), _definition(links))
        ]
        if conflicts:
            if report is not None:
                _increment(report, "bom_repeated_subassemblies")
                _increment(report, "bom_definition_conflicts")
                _increment(
                    report,
                    "tree_links_skipped_integrity",
                    sum(len(group) for group in copies.values()),
                )
            _issue(
                report,
                "error",
                "treebom.integrity",
                "Repeated subassembly has conflicting child quantities; its BOM was blocked.",
                file=source_name,
                part_number=parent[0],
                paths=list(copies),
            )
            if report is not None:
                report["bom_integrity_status"] = "conflict"
            continue
        output.extend(first_links)
        if len(values) > 1:
            if report is not None:
                report["bom_integrity_status"] = "warning"
                _increment(report, "bom_repeated_subassemblies")
                _increment(
                    report,
                    "bom_repeated_subassembly_copies_collapsed",
                    len(values) - 1,
                )
            _issue(
                report,
                "warning",
                "treebom.integrity",
                "Identical repeated subassembly definitions were collapsed.",
                file=source_name,
                part_number=parent[0],
                canonical_path=first_path,
                paths=list(copies),
            )
    return output
def _aggregate_links(
    links: Iterable[tuple[str, str, str, str, float, object]],
) -> list[tuple[str, str, str, str, float, list[dict[str, Any]]]]:
    totals: dict[tuple[str, str, str, str], float] = defaultdict(float)
    occurrences: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for ppn, prev, cpn, crev, qty, sequence in links:
        key = (_base_pn(ppn), clean_rev(prev), _base_pn(cpn), clean_rev(crev))
        if not key[0] or not key[2]:
            continue
        totals[key] += float(qty or 0)
        occurrences[key].append({"seq": sequence, "qty": float(qty or 0)})
    return [
        (*key, quantity, occurrences[key])
        for key, quantity in sorted(totals.items())
    ]
def import_bom_zip(
    file_bytes: bytes,
    filename: str,
    seed_tag: str = "upload",
    *,
    scan_artifacts: bool = True,
    generate_thumbs: bool = True,
    override_mode: str = DEFAULT_OVERRIDE_MODE,
    **options: Any,
) -> dict[str, Any]:
    """Compatibility wrapper around the single upload-pack implementation."""
    from app.services.upload_pack import import_upload_pack
    result = import_upload_pack(
        file_bytes,
        filename,
        dry_run=False,
        allow_extra=False,
        seed_tag=seed_tag,
        override_mode=override_mode,
        scan_artifacts=scan_artifacts,
        generate_thumbs=generate_thumbs,
        **options,
    )
    report = dict(result.get("import") or {})
    report.setdefault("zip", filename)
    report.setdefault("override_mode", normalize_override_mode(override_mode))
    return report
