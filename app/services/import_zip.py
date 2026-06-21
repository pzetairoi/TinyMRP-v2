# app/services/import_zip.py
import ast, io, json, zipfile, re, traceback, os, time
from datetime import datetime
from typing import Dict, Any, List, Tuple, Iterable, Set
from mongoengine import NotUniqueError
from mongoengine.queryset.visitor import Q
from app.models.part import Part
from app.models.bom import BOMLink
from app.services.thumbs_gen import generate_thumbs_for_parts
from collections import defaultdict

# Import necessary services for file scanning and upserting
from app.services.filescan import discover_part_files, upsert_part_files_detailed
# Import necessary services for attributes normalization and merging
from app.services.attrs import approved_value, harvest_part_attrs, process_attributes
from app.services.canonical_fields import sync_part_canonical_fields
from app.services.part_annotations import migrate_legacy_annotations
from app.services.processmeta import normalize_processes
from app.services.part_norm import clean_rev, clean_pn, clean_qty


from flask import current_app
try:
    from app.services.metrics import timed_span
except Exception:
    from contextlib import contextmanager
    @contextmanager
    def timed_span(_name: str):
        yield


def _stage_start() -> Tuple[float, float]:
    return (time.perf_counter(), time.process_time())


def _stage_end(report: Dict[str, Any], name: str, start: Tuple[float, float]) -> None:
    if report is None or not name:
        return
    try:
        t0, c0 = start
        t1 = time.perf_counter()
        c1 = time.process_time()
        elapsed = float(t1 - t0)
        cpu = float(c1 - c0)
        idle = float(max(0.0, elapsed - cpu))
        timings = report.get("timings")
        if not isinstance(timings, dict):
            timings = {}
            report["timings"] = timings
        timings[name] = {"elapsed_s": elapsed, "cpu_s": cpu, "idle_s": idle}
    except Exception:
        pass


def _snapshot_resources() -> Dict[str, Any]:
    snap: Dict[str, Any] = {
        "utc": datetime.utcnow().isoformat(),
        "cpu_s": float(time.process_time()),
    }
    try:
        snap["pid"] = int(os.getpid())
    except Exception:
        pass
    try:
        import psutil  # type: ignore

        snap["rss_bytes"] = int(psutil.Process().memory_info().rss)
    except Exception:
        snap["rss_bytes"] = None
    return snap


_PART_OVERRIDE_MODE_DEFAULT = "unless_existing_approved"
_PART_OVERRIDE_MODE_ALIASES = {
    "default": _PART_OVERRIDE_MODE_DEFAULT,
    "override_unless_existing_approved": _PART_OVERRIDE_MODE_DEFAULT,
    "override_unless_approved": _PART_OVERRIDE_MODE_DEFAULT,
}
_PART_OVERRIDE_MODES = {_PART_OVERRIDE_MODE_DEFAULT, "preserve", "approved_only", "always"}
_REPORT_ATTR_EXCLUDE_KEYS = {"seed", "comments_search"}


def _override_mode(value: object) -> str:
    mode = str(value or _PART_OVERRIDE_MODE_DEFAULT).strip().lower()
    mode = _PART_OVERRIDE_MODE_ALIASES.get(mode, mode)
    return mode if mode in _PART_OVERRIDE_MODES else _PART_OVERRIDE_MODE_DEFAULT


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _merge_attrs_preserve(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing or {})
    for key, value in (incoming or {}).items():
        if not _has_value(merged.get(key)) and _has_value(value):
            merged[key] = value
    return merged


def _merge_attrs_replace(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    return dict(incoming or {})


def _should_replace_existing(existing_attrs: Dict[str, Any], incoming_attrs: Dict[str, Any], override_mode: str) -> bool:
    mode = _override_mode(override_mode)
    existing_approved = bool(approved_value(existing_attrs or {}))
    incoming_approved = bool(approved_value(incoming_attrs or {}))
    if mode == "always":
        return True
    if mode == _PART_OVERRIDE_MODE_DEFAULT:
        return not existing_approved
    if mode != "approved_only":
        return False
    return incoming_approved and not existing_approved


def _apply_part_update(
    part: Part,
    norm: Dict[str, Any],
    *,
    seed_tag: str,
    override_mode: str,
) -> None:
    incoming_attrs = dict(norm.get("attrs") or {})
    incoming_attrs["seed"] = seed_tag
    _, incoming_processes = process_attributes(incoming_attrs)
    hardware_override = _is_hardware_by_folder(incoming_attrs) or _is_hardware_by_process(incoming_attrs)
    if hardware_override:
        incoming_processes = ["hardware"]

    is_new = part.id is None
    if not is_new:
        try:
            migrate_legacy_annotations(part)
        except Exception:
            pass
    existing_attrs = dict(getattr(part, "attrs", {}) or {})
    replace_existing = is_new or _should_replace_existing(existing_attrs, incoming_attrs, override_mode)

    if replace_existing:
        part.description = norm.get("description") or ""
        part.category = norm.get("category") or ""
        part.uom = norm.get("uom") or "EA"
        part.attrs = _merge_attrs_replace(existing_attrs, incoming_attrs)
        sync_part_canonical_fields(
            part,
            raw_attrs=part.attrs,
            top_level_overrides={
                "description": part.description,
                "revision": norm.get("revision") or part.revision or "",
                "category": part.category,
                "uom": part.uom,
            },
            process_override=incoming_processes if incoming_processes or hardware_override else None,
        )
        if not incoming_processes and is_new:
            part.processes = []
        return

    if not _has_value(getattr(part, "description", None)):
        part.description = norm.get("description") or ""
    if not _has_value(getattr(part, "category", None)):
        part.category = norm.get("category") or ""
    if not _has_value(getattr(part, "uom", None)):
        part.uom = norm.get("uom") or "EA"
    part.attrs = _merge_attrs_preserve(existing_attrs, incoming_attrs)
    sync_part_canonical_fields(
        part,
        raw_attrs=part.attrs,
        top_level_overrides={
            "description": part.description or norm.get("description") or "",
            "revision": norm.get("revision") or part.revision or "",
            "category": part.category or norm.get("category") or "",
            "uom": part.uom or norm.get("uom") or "EA",
        },
        process_override=incoming_processes if incoming_processes or hardware_override else None,
    )


def _report_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _report_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_report_value(v) for v in value]
    return str(value)


def _part_snapshot(part: Part) -> Dict[str, Any]:
    return {
        "description": str(getattr(part, "description", "") or ""),
        "category": str(getattr(part, "category", "") or ""),
        "uom": str(getattr(part, "uom", "") or ""),
        "processes": list(getattr(part, "processes", None) or []),
        "attrs": dict(getattr(part, "attrs", {}) or {}),
    }


def _diff_part_snapshot(before: Dict[str, Any], after: Dict[str, Any]) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []
    for field_name in ("description", "category", "uom", "processes"):
        before_value = _report_value((before or {}).get(field_name))
        after_value = _report_value((after or {}).get(field_name))
        if before_value != after_value:
            changes.append(
                {
                    "scope": "part",
                    "field": field_name,
                    "before": before_value,
                    "after": after_value,
                }
            )

    before_attrs = dict((before or {}).get("attrs") or {})
    after_attrs = dict((after or {}).get("attrs") or {})
    attr_keys = sorted({str(k) for k in before_attrs.keys()} | {str(k) for k in after_attrs.keys()})
    for field_name in attr_keys:
        if field_name in _REPORT_ATTR_EXCLUDE_KEYS:
            continue
        before_value = _report_value(before_attrs.get(field_name))
        after_value = _report_value(after_attrs.get(field_name))
        if before_value != after_value:
            changes.append(
                {
                    "scope": "attribute",
                    "field": field_name,
                    "before": before_value,
                    "after": after_value,
                }
            )
    return changes


def _snapshot_bom_children(parents: Iterable[Tuple[str, str]]) -> Dict[Tuple[str, str], Dict[Tuple[str, str], float]]:
    snapshots: Dict[Tuple[str, str], Dict[Tuple[str, str], float]] = {}
    for parent_pn, parent_rev in parents:
        target_pn = _norm_pn(parent_pn)
        target_rev = clean_rev(parent_rev)
        if not target_pn:
            continue
        pn_pattern = _pn_regex(target_pn)
        if not pn_pattern:
            continue
        children: Dict[Tuple[str, str], float] = {}
        q = BOMLink.objects(parent_pn__iregex=pn_pattern).only(
            "parent_pn",
            "parent_rev",
            "child_pn",
            "child_rev",
            "qty",
        )
        for link in q:
            link_parent_pn = _norm_pn(getattr(link, "parent_pn", ""))
            link_parent_rev = clean_rev(getattr(link, "parent_rev", ""))
            if link_parent_pn != target_pn or link_parent_rev != target_rev:
                continue
            child_key = (
                _norm_pn(getattr(link, "child_pn", "")),
                clean_rev(getattr(link, "child_rev", "")),
            )
            if not child_key[0]:
                continue
            children[child_key] = float(getattr(link, "qty", 0.0) or 0.0)
        snapshots[(target_pn, target_rev)] = children
    return snapshots


def _children_from_links(
    links: Iterable[Tuple[str, str, str, str, float, List[Dict[str, Any]]]]
) -> Dict[Tuple[str, str], Dict[Tuple[str, str], float]]:
    out: Dict[Tuple[str, str], Dict[Tuple[str, str], float]] = {}
    for parent_pn, parent_rev, child_pn, child_rev, qty, _occs in links:
        parent_key = (_norm_pn(parent_pn), clean_rev(parent_rev))
        child_key = (_norm_pn(child_pn), clean_rev(child_rev))
        if not parent_key[0] or not child_key[0]:
            continue
        out.setdefault(parent_key, {})[child_key] = float(qty or 0.0)
    return out


def _bom_child_row(child_key: Tuple[str, str], qty: float) -> Dict[str, Any]:
    return {
        "part_number": child_key[0],
        "revision": child_key[1],
        "qty": float(qty or 0.0),
    }


def _diff_bom_children(
    before: Dict[Tuple[str, str], float],
    after: Dict[Tuple[str, str], float],
) -> Dict[str, Any] | None:
    before = dict(before or {})
    after = dict(after or {})
    before_keys = set(before.keys())
    after_keys = set(after.keys())
    added = [_bom_child_row(key, after[key]) for key in sorted(after_keys - before_keys)]
    removed = [_bom_child_row(key, before[key]) for key in sorted(before_keys - after_keys)]
    qty_changed: List[Dict[str, Any]] = []
    for key in sorted(before_keys & after_keys):
        before_qty = float(before.get(key, 0.0) or 0.0)
        after_qty = float(after.get(key, 0.0) or 0.0)
        if before_qty != after_qty:
            qty_changed.append(
                {
                    "part_number": key[0],
                    "revision": key[1],
                    "before_qty": before_qty,
                    "after_qty": after_qty,
                }
            )
    if not added and not removed and not qty_changed:
        return None
    return {
        "before_children": len(before),
        "after_children": len(after),
        "added": added,
        "removed": removed,
        "qty_changed": qty_changed,
    }


def _ensure_modified_part(
    modified_parts: Dict[Tuple[str, str], Dict[str, Any]],
    pn: str,
    rev: str,
) -> Dict[str, Any]:
    key = (_norm_pn(pn), clean_rev(rev))
    entry = modified_parts.get(key)
    if entry is None:
        entry = {
            "part_number": key[0],
            "revision": key[1],
            "data_changes": [],
            "bom_changes": None,
            "file_changes": [],
        }
        modified_parts[key] = entry
    return entry

def _report_inc(report: Dict[str, Any], key: str, delta: int = 1) -> None:
    if report is None:
        return
    try:
        report[key] = int(report.get(key) or 0) + int(delta)
    except Exception:
        report[key] = report.get(key) or 0


def _report_issue(
    report: Dict[str, Any],
    level: str,
    *,
    stage: str,
    file: str = "",
    line_number: int = 0,
    part_number: str = "",
    path: str = "",
    message: str = "",
    exc: Exception = None,
    include_traceback: bool = False,
) -> None:
    if report is None:
        return

    key = "errors" if str(level).lower() == "error" else "warnings"
    try:
        items = report.get(key)
        if not isinstance(items, list):
            items = []
            report[key] = items
    except Exception:
        items = []
        report[key] = items

    entry: Dict[str, Any] = {
        "stage": stage or "",
        "file": file or "",
        "line_number": int(line_number or 0),
        "part_number": part_number or "",
        "path": path or "",
        "message": message or "",
    }
    if exc is not None:
        entry["exception_type"] = type(exc).__name__
        entry["exception_message"] = str(exc)
        if include_traceback:
            try:
                entry["traceback"] = traceback.format_exc()
            except Exception:
                pass

    items.append(entry)


def _base_pn(pn: str) -> str:
    if not pn:
        return ""
    return clean_pn(str(pn).split("^", 1)[0])

def _norm_pn(pn: object) -> str:
    return _base_pn(pn).strip()

def _pn_regex(pn: str) -> str:
    tokens = [re.escape(t) for t in re.split(r"\s+", str(pn).strip()) if t]
    if not tokens:
        return ""
    return r"^\s*" + r"\s+".join(tokens) + r"\s*$"

def _parse_flatbom(
    txt: str,
    source_name: str = "",
    max_warnings: int = 3,
    report: Dict[str, Any] = None,
) -> List[Tuple[int, Dict[str, Any]]]:
    """
    FLATBOM contains one dict per line (JSON or Python-like with single quotes).
    We remove literal '...' sequences and parse each line safely.
    """
    out: List[Tuple[int, Dict[str, Any]]] = []
    failures = 0
    logger = None
    try:
        logger = current_app.logger
    except Exception:
        logger = None

    txt = (txt or "").lstrip("\ufeff")
    for line_no, raw in enumerate((txt or "").splitlines(), start=1):
        line = (raw or "").strip()
        if not line:
            continue
        line = line.lstrip("\ufeff")
        cleaned = line.replace("...", "")

        d = None
        try:
            d = json.loads(cleaned)
        except Exception:
            try:
                d = ast.literal_eval(cleaned)
            except Exception as exc:
                if logger and failures < max_warnings:
                    preview = line.replace("\t", " ")
                    preview = preview[:160]
                    label = source_name or "FLATBOM"
                    logger.warning("FLATBOM parse failed (%s) line=%s: %s", label, line_no, preview)
                failures += 1
                _report_inc(report, "flat_lines_failed_parse", 1)
                _report_issue(
                    report,
                    "error",
                    stage="flatbom.parse",
                    file=source_name,
                    line_number=line_no,
                    message="Failed to parse FLATBOM line.",
                    exc=exc,
                )
                continue

        if not isinstance(d, dict):
            _report_inc(report, "flat_lines_skipped_not_dict", 1)
            _report_issue(
                report,
                "warning",
                stage="flatbom.parse",
                file=source_name,
                line_number=line_no,
                message="FLATBOM line did not evaluate to a dict (skipped).",
            )
            continue

        clean: Dict[str, Any] = {}
        for k, v in d.items():
            if k is None:
                continue
            try:
                kk = str(k).strip()
            except Exception:
                continue
            if not kk:
                continue
            if isinstance(v, str):
                try:
                    v = v.strip()
                except Exception:
                    pass
            clean[kk] = v
        out.append((line_no, clean))

    return out

def _attr_ci_value(attrs: Dict[str, Any], key: str) -> List[str]:
    if not isinstance(attrs, dict):
        return []
    key_l = (key or "").strip().lower()
    hits: List[str] = []
    for k, v in attrs.items():
        try:
            if str(k or "").strip().lower() != key_l:
                continue
        except Exception:
            continue
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            hits.extend([str(x) for x in v if x is not None])
        else:
            hits.append(str(v))
    return hits

def _hardware_folder_tokens() -> List[str]:
    cfg = current_app.config.get("HARDWARE_FOLDERS") or []
    raw: List[str] = []
    if isinstance(cfg, str):
        raw = [p for p in re.split(r"[;,]", cfg) if p.strip()]
    else:
        for item in cfg:
            if item is None:
                continue
            raw.append(str(item))
    tokens: List[str] = []
    for item in raw:
        for chunk in re.split(r"[^A-Za-z0-9]+", str(item)):
            t = chunk.strip().lower()
            if not t:
                continue
            tokens.append(t)
            if t.endswith("ies") and len(t) > 3:
                tokens.append(t[:-3] + "y")
            if t.endswith("es") and len(t) > 2:
                tokens.append(t[:-2])
            if t.endswith("s") and len(t) > 1:
                tokens.append(t[:-1])
    seen: Set[str] = set()
    out: List[str] = []
    for t in tokens:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out

def _path_text_from_attrs(attrs: Dict[str, Any]) -> str:
    text_parts: List[str] = []
    for key in ("folder", "file", "filepath", "path", "nativepath", "native_file", "file_path"):
        text_parts.extend(_attr_ci_value(attrs, key))
    return " ".join(text_parts).lower()

def _is_hardware_by_folder(attrs: Dict[str, Any]) -> bool:
    tokens = _hardware_folder_tokens()
    if not tokens:
        return False
    path_text = _path_text_from_attrs(attrs)
    if not path_text:
        return False
    path_text = path_text.lower()
    words = [w for w in re.split(r"[^a-z0-9]+", path_text) if w]
    for t in tokens:
        if t in path_text:
            return True
        for w in words:
            if t in w:
                return True
    return False

def _is_hardware_by_process(attrs: Dict[str, Any]) -> bool:
    meta = current_app.config.get("PROCESS_META", {}) or {}
    try:
        procs = normalize_processes(attrs, meta)
    except Exception:
        procs = []
    return "hardware" in (p for p in procs if p)

def _normalize_part(d: Dict[str, Any]) -> Dict[str, Any]:
    low = { (k.strip().lower() if isinstance(k, str) else k): v for k, v in d.items() }
    pn = low.get("partnumber") or low.get("part_number") or low.get("pn") or ""
    pn = _base_pn(str(pn))
    # description preference
    desc = (low.get("description") or "") or ""
    for k in ("desc1","desc2","desc3","desc"):
        if k in low and low[k]:
            desc = (f"{desc} {low[k]}").strip()
    category = low.get("category") or ""
    uom = low.get("uom") or "EA"
    revision = clean_rev(low.get("revision") or low.get("rev") or "")

    return {
        "part_number": pn,
        "description": (desc or "").strip(),
        "category": (str(category) if category is not None else "").strip(),
        "uom": (str(uom) if uom is not None else "EA").strip() or "EA",
        "revision": clean_rev(revision),
        "attrs": d,  # store full original dict
    }

def _item_seq(item_no: str) -> object:
    if not item_no:
        return ""
    seg = item_no.split(".")[-1].strip()
    if not seg:
        return ""
    try:
        return int(seg)
    except Exception:
        return seg


def _parse_treebom(
    txt: str,
    source_name: str = "",
    report: Dict[str, Any] = None,
) -> List[Tuple[str, str, str, str, float, object]]:
    """
    TREEBOM is a tab-separated table with headers:
      ITEM NO. | PART NUMBER | Revision | QTY.
    Item numbers like 1, 1.2, 1.2.3 denote hierarchy.

    Returns a list of (parent_pn, parent_rev, child_pn, child_rev, qty, seq).
    """
    lines = txt.splitlines()
    rows = []
    for line_no, line in enumerate(lines, start=1):
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        if parts[0].strip() == "ITEM NO.":
            continue
        item_no = parts[0].strip()
        pn_raw = (parts[1] or "").strip()
        if not pn_raw:
            _report_inc(report, "rows_skipped_blank_part", 1)
            _report_issue(
                report,
                "warning",
                stage="treebom.parse",
                file=source_name,
                line_number=line_no,
                message=f"TREEBOM row skipped: blank PART NUMBER (item={item_no}).",
            )
            continue

        part_number = clean_pn(pn_raw)
        if not part_number:
            _report_inc(report, "rows_skipped_blank_part", 1)
            _report_issue(
                report,
                "warning",
                stage="treebom.parse",
                file=source_name,
                line_number=line_no,
                message=f"TREEBOM row skipped: PART NUMBER cleaned to empty (item={item_no}).",
            )
            continue
        revision = clean_rev(parts[2].strip())
        qty_raw = (parts[3] or "").strip()
        if not qty_raw:
            qty = 1.0
        else:
            try:
                qty = float(qty_raw)
            except Exception as exc:
                _report_inc(report, "tree_rows_failed_qty", 1)
                _report_issue(
                    report,
                    "error",
                    stage="treebom.parse",
                    file=source_name,
                    line_number=line_no,
                    part_number=_base_pn(part_number),
                    message=f"TREEBOM row skipped: failed to parse QTY (item={item_no}).",
                    exc=exc,
                )
                continue
        rows.append({"item_no": item_no, "part_number": part_number, "revision": revision, "qty": qty})

    # Map item_no -> (pn, revision) then build links
    item_to_part: Dict[str, Tuple[str, str]] = {}
    for r in rows:
        pn = _base_pn(r["part_number"])
        rev = clean_rev(r.get("revision") or "")
        item_to_part[r["item_no"]] = (pn, rev)

    links: List[Tuple[str, str, str, str, float, object]] = []
    for r in rows:
        item = r["item_no"]
        child_entry = item_to_part.get(item)
        if not child_entry or item == "1":
            continue
        child_pn, child_rev = child_entry
        # find nearest ancestor with a PN
        parent_item = item.rsplit(".", 1)[0] if "." in item else ""
        while parent_item and not item_to_part.get(parent_item):
            parent_item = parent_item.rsplit(".", 1)[0] if "." in parent_item else ""
        if not parent_item:
            continue
        parent_pn, parent_rev = item_to_part[parent_item]
        if not parent_pn or parent_pn == child_pn:
            continue
        qty = clean_qty(r["qty"])
        seq = _item_seq(item)
        links.append((parent_pn, parent_rev, child_pn, child_rev, qty, seq))
    return links

def _aggregate_links(
    links: Iterable[Tuple[str, str, str, str, float, object]]
) -> List[Tuple[str, str, str, str, float, List[Dict[str, Any]]]]:
    totals: Dict[Tuple[str, str, str, str], float] = {}
    occurrences: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = {}
    for parent_pn, parent_rev, child_pn, child_rev, qty, seq in links:
        key = (
            _norm_pn(parent_pn),
            clean_rev(parent_rev),
            _norm_pn(child_pn),
            clean_rev(child_rev),
        )
        if not key[0] or not key[2]:
            continue
        qty_val = float(qty or 0.0)
        totals[key] = totals.get(key, 0.0) + qty_val
        occurrences.setdefault(key, []).append({"seq": seq, "qty": qty_val})
    out: List[Tuple[str, str, str, str, float, List[Dict[str, Any]]]] = []
    for (ppn, prev, cpn, crev), qty in totals.items():
        out.append((ppn, prev, cpn, crev, qty, occurrences.get((ppn, prev, cpn, crev), [])))
    out.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
    return out

def _ensure_part_exists(pn: str, rev: str, seed_tag: str) -> bool:
    pn = _norm_pn(pn)
    rev = clean_rev(rev)
    if not pn:
        return False
    if Part.objects(part_number=pn, revision=rev).first():
        return False
    try:
        Part(part_number=pn, revision=rev, description="", uom="EA", attrs={"seed": seed_tag}).save()
        return True
    except NotUniqueError:
        return False

def _find_existing_link(parent_pn: str, parent_rev: str, child_pn: str, child_rev: str):
    query = dict(parent_pn=parent_pn, child_pn=child_pn)
    if "parent_rev" in BOMLink._fields and "child_rev" in BOMLink._fields:
        query.update(parent_rev=parent_rev, child_rev=child_rev)
    existing_links = list(BOMLink.objects(**query))

    if not existing_links:
        return None, []

    existing_links.sort(key=lambda link: link.updated_at or link.id, reverse=True)
    return existing_links[0], existing_links[1:]

def _clear_existing_links(parents: Iterable[Tuple[str, str]]) -> int:
    removed = 0
    for parent_pn, parent_rev in parents:
        target_pn = _norm_pn(parent_pn)
        if not target_pn:
            continue
        target_rev = clean_rev(parent_rev)
        pn_pattern = _pn_regex(target_pn)
        if not pn_pattern:
            continue
        q = BOMLink.objects(parent_pn__iregex=pn_pattern).only("id", "parent_pn", "parent_rev")
        for link in q:
            link_pn = _norm_pn(getattr(link, "parent_pn", ""))
            if link_pn != target_pn:
                continue
            link_rev = clean_rev(getattr(link, "parent_rev", ""))
            if link_rev != target_rev:
                continue
            link.delete()
            removed += 1
    return removed

def _dedupe_links_for_parents(parents: Iterable[Tuple[str, str]]) -> int:
    removed = 0
    for parent_pn, parent_rev in parents:
        target_pn = _norm_pn(parent_pn)
        if not target_pn:
            continue
        target_rev = clean_rev(parent_rev)
        pn_pattern = _pn_regex(target_pn)
        if not pn_pattern:
            continue
        q = BOMLink.objects(parent_pn__iregex=pn_pattern).only(
            "id",
            "parent_pn",
            "parent_rev",
            "child_pn",
            "child_rev",
            "updated_at",
        )
        groups: Dict[Tuple[str, str, str, str], List[BOMLink]] = {}
        for link in q:
            link_parent_pn = _norm_pn(getattr(link, "parent_pn", ""))
            if link_parent_pn != target_pn:
                continue
            link_parent_rev = clean_rev(getattr(link, "parent_rev", ""))
            if link_parent_rev != target_rev:
                continue
            key = (
                link_parent_pn,
                link_parent_rev,
                _norm_pn(getattr(link, "child_pn", "")),
                clean_rev(getattr(link, "child_rev", "")),
            )
            groups.setdefault(key, []).append(link)

        for key, links in groups.items():
            if len(links) <= 1:
                link = links[0]
                if (
                    link.parent_pn != key[0]
                    or clean_rev(getattr(link, "parent_rev", "")) != key[1]
                    or link.child_pn != key[2]
                    or clean_rev(getattr(link, "child_rev", "")) != key[3]
                ):
                    link.parent_pn = key[0]
                    link.parent_rev = key[1]
                    link.child_pn = key[2]
                    link.child_rev = key[3]
                    link.save()
                continue
            links.sort(key=lambda l: (l.updated_at or datetime.min, l.id), reverse=True)
            keep = links[0]
            for dup in links[1:]:
                dup.delete()
                removed += 1
            if (
                keep.parent_pn != key[0]
                or clean_rev(getattr(keep, "parent_rev", "")) != key[1]
                or keep.child_pn != key[2]
                or clean_rev(getattr(keep, "child_rev", "")) != key[3]
            ):
                keep.parent_pn = key[0]
                keep.parent_rev = key[1]
                keep.child_pn = key[2]
                keep.child_rev = key[3]
                keep.save()
    return removed

def import_bom_zip(
    file_bytes: bytes,
    filename: str,
    seed_tag: str = "upload",
    *,
    scan_artifacts: bool = True,
    generate_thumbs: bool = True,
    override_mode: str = _PART_OVERRIDE_MODE_DEFAULT,
) -> Dict[str, Any]:
    """
    Main entry: import a single ZIP file.
    Creates/updates Parts from FLATBOM and links from TREEBOM.
    Stores all properties under Part.attrs.
    """
    report: Dict[str, Any] = {
        "zip": filename,
        "flatbom_file": "",
        "treebom_file": "",
        "root": None,
        "root_revision": "",
        "parts_created": 0,
        "parts_updated": 0,
        "modified_parts_count": 0,
        "modified_parts": [],
        "links_created": 0,
        "links_skipped": 0,
        "links_removed": 0,
        "parts_seeded": 0,
        "parts_seeded_list": [],
        "parts_with_props": 0,
        "artifacts_added": 0,
        "artifacts_found_by_type": {},
        "thumbnails_built": 0,
        "thumbnails_generated": 0,
        "override_mode": _override_mode(override_mode),
        # diagnostics / best-effort counters
        "rows_skipped_blank_part": 0,
        "flat_lines_failed_parse": 0,
        "flat_lines_skipped_not_dict": 0,
        "flat_lines_failed_normalize": 0,
        "tree_rows_failed_qty": 0,
        "errors": [],
        "warnings": [],
        "timings": {},
        "resources_start": {},
        "resources_end": {},
    }

    report["resources_start"] = _snapshot_resources()
    total_start = _stage_start()

    with timed_span("import.bom.total"):
        try:
            zf = zipfile.ZipFile(io.BytesIO(file_bytes))
        except Exception as exc:
            _report_issue(
                report,
                "error",
                stage="zip.open",
                file=filename,
                message="Failed to open ZIP file.",
                exc=exc,
                include_traceback=True,
            )
            raise ValueError("invalid zip")

        with zf:
            scan_start = _stage_start()
            # find the first *_FLATBOM.txt and *_TREEBOM.txt
            try:
                flat_name = next(
                    (n for n in zf.namelist() if n.endswith("_FLATBOM.txt") and not n.endswith("/")),
                    None,
                )
            except Exception:
                flat_name = None
            try:
                tree_name = next(
                    (n for n in zf.namelist() if n.endswith("_TREEBOM.txt") and not n.endswith("/")),
                    None,
                )
            except Exception:
                tree_name = None

            report["flatbom_file"] = flat_name or ""
            report["treebom_file"] = tree_name or ""

            if not flat_name:
                _report_issue(report, "warning", stage="zip.scan", message="No *_FLATBOM.txt found in ZIP.")
            if not tree_name:
                _report_issue(report, "warning", stage="zip.scan", message="No *_TREEBOM.txt found in ZIP.")
            _stage_end(report, "zip.scan", scan_start)

            created_parts = 0
            updated_parts = 0
            created_links = 0
            removed_links = 0
            skipped_links = 0
            tree_parts: Set[Tuple[str, str]] = set()
            seeded_parts: Set[Tuple[str, str]] = set()
            part_existed_before: Dict[Tuple[str, str], bool] = {}
            modified_parts: Dict[Tuple[str, str], Dict[str, Any]] = {}

            # 1) Parts from FLATBOM
            part_props: Dict[Tuple[str, str], Dict[str, Any]] = {}
            part_line: Dict[Tuple[str, str], int] = {}
            if flat_name:
                flat_read_start = _stage_start()
                flat_txt = ""
                try:
                    with timed_span("import.bom.flatbom.read"):
                        flat_txt = zf.read(flat_name).decode("utf-8-sig", errors="replace")
                except Exception as exc:
                    _report_issue(
                        report,
                        "error",
                        stage="flatbom.read",
                        file=flat_name,
                        message="Failed to read FLATBOM.",
                        exc=exc,
                    )
                    flat_txt = ""
                _stage_end(report, "flatbom.read", flat_read_start)

                flat_parse_start = _stage_start()
                with timed_span("import.bom.flatbom.parse"):
                    for line_no, d in _parse_flatbom(flat_txt, source_name=flat_name, report=report):
                        try:
                            norm = _normalize_part(d)
                        except Exception as exc:
                            _report_inc(report, "flat_lines_failed_normalize", 1)
                            _report_issue(
                                report,
                                "error",
                                stage="flatbom.normalize",
                                file=flat_name,
                                line_number=line_no,
                                message="Failed to normalize FLATBOM dict.",
                                exc=exc,
                            )
                            continue

                        pn = norm.get("part_number") or ""
                        rev = clean_rev(norm.get("revision") or "")
                        if not pn:
                            _report_issue(
                                report,
                                "warning",
                                stage="flatbom.normalize",
                                file=flat_name,
                                line_number=line_no,
                                message="FLATBOM row skipped: blank part number.",
                            )
                            continue

                        key = (pn, rev)
                        part_props[key] = norm
                        part_line[key] = line_no
                _stage_end(report, "flatbom.parse", flat_parse_start)

            # Upsert parts (best effort)
            parts_upsert_start = _stage_start()
            with timed_span("import.bom.parts.upsert"):
                for (pn, rev), norm in part_props.items():
                    pn = _norm_pn(pn)
                    rev = clean_rev(rev)
                    if not pn:
                        continue

                    try:
                        p = Part.objects(part_number=pn, revision=rev).first()
                        is_new = p is None
                        part_existed_before[(pn, rev)] = not is_new
                        before_snapshot = _part_snapshot(p) if p is not None else None
                        if p is None:
                            p = Part(part_number=pn, revision=rev)

                        _apply_part_update(
                            p,
                            norm,
                            seed_tag=seed_tag,
                            override_mode=override_mode,
                        )
                        p.save()
                        if is_new:
                            created_parts += 1
                        else:
                            updated_parts += 1
                            changes = _diff_part_snapshot(before_snapshot or {}, _part_snapshot(p))
                            if changes:
                                entry = _ensure_modified_part(modified_parts, pn, rev)
                                entry["data_changes"] = changes
                    except NotUniqueError:
                        try:
                            existing = Part.objects(part_number=pn, revision=rev).first()
                            if not existing:
                                raise
                            part_existed_before[(pn, rev)] = True
                            before_snapshot = _part_snapshot(existing)
                            _apply_part_update(
                                existing,
                                norm,
                                seed_tag=seed_tag,
                                override_mode=override_mode,
                            )
                            existing.save()
                            updated_parts += 1
                            changes = _diff_part_snapshot(before_snapshot, _part_snapshot(existing))
                            if changes:
                                entry = _ensure_modified_part(modified_parts, pn, rev)
                                entry["data_changes"] = changes
                        except Exception as exc:
                            _report_issue(
                                report,
                                "error",
                                stage="parts.upsert",
                                part_number=pn,
                                line_number=part_line.get((pn, rev), 0),
                                message="Failed to upsert part after NotUniqueError.",
                                exc=exc,
                            )
                    except Exception as exc:
                        _report_issue(
                            report,
                            "error",
                            stage="parts.upsert",
                            part_number=pn,
                            line_number=part_line.get((pn, rev), 0),
                            message="Failed to upsert part.",
                            exc=exc,
                        )
            _stage_end(report, "parts.upsert", parts_upsert_start)

            # 2) Links from TREEBOM (best effort)
            links: List[Tuple[str, str, str, str, float, List[Dict[str, Any]]]] = []
            if tree_name:
                tree_read_start = _stage_start()
                tree_txt = ""
                try:
                    with timed_span("import.bom.tree.read"):
                        tree_txt = zf.read(tree_name).decode("utf-8-sig", errors="replace")
                except Exception as exc:
                    _report_issue(
                        report,
                        "error",
                        stage="treebom.read",
                        file=tree_name,
                        message="Failed to read TREEBOM.",
                        exc=exc,
                    )
                    tree_txt = ""
                _stage_end(report, "treebom.read", tree_read_start)

                try:
                    tree_parse_start = _stage_start()
                    with timed_span("import.bom.tree.parse"):
                        links = _aggregate_links(_parse_treebom(tree_txt, source_name=tree_name, report=report))
                    _stage_end(report, "treebom.parse", tree_parse_start)
                except Exception as exc:
                    _report_issue(
                        report,
                        "error",
                        stage="treebom.parse",
                        file=tree_name,
                        message="Failed to parse TREEBOM.",
                        exc=exc,
                        include_traceback=True,
                    )
                    links = []

                parent_pairs = {(p, clean_rev(r)) for p, r, _, _, _, _ in links if p}
                existing_parent_pairs = {pair for pair in parent_pairs if part_existed_before.get(pair)}
                bom_before = _snapshot_bom_children(existing_parent_pairs) if existing_parent_pairs else {}
                if parent_pairs:
                    try:
                        clear_links_start = _stage_start()
                        removed_links = _clear_existing_links(parent_pairs)
                        _stage_end(report, "links.clear", clear_links_start)
                    except Exception as exc:
                        _report_issue(
                            report,
                            "error",
                            stage="links.clear",
                            message="Failed to clear existing BOM links for parents.",
                            exc=exc,
                        )

                links_save_start = _stage_start()
                with timed_span("import.bom.links.save"):
                    for parent_pn, parent_rev, child_pn, child_rev, qty, occs in links:
                        if not parent_pn or not child_pn:
                            skipped_links += 1
                            continue

                        parent_pn = _norm_pn(parent_pn)
                        child_pn = _norm_pn(child_pn)
                        parent_rev = clean_rev(parent_rev)
                        child_rev = clean_rev(child_rev)
                        if not parent_pn or not child_pn:
                            skipped_links += 1
                            continue

                        tree_parts.add((parent_pn, parent_rev))
                        tree_parts.add((child_pn, child_rev))

                        try:
                            # ensure parts exist (create shells if missing)
                            for pn, rev in ((parent_pn, parent_rev), (child_pn, child_rev)):
                                try:
                                    if _ensure_part_exists(pn, rev, seed_tag):
                                        created_parts += 1
                                        seeded_parts.add((_base_pn(pn), clean_rev(rev)))
                                except Exception as exc:
                                    _report_issue(
                                        report,
                                        "error",
                                        stage="parts.seed",
                                        part_number=pn,
                                        message="Failed to ensure part exists for BOM link.",
                                        exc=exc,
                                    )

                            existing, duplicates = _find_existing_link(parent_pn, parent_rev, child_pn, child_rev)
                            if duplicates:
                                for dup in duplicates:
                                    try:
                                        dup.delete()
                                    except Exception:
                                        pass

                            if existing:
                                existing.qty = qty
                                existing.uom = existing.uom or "EA"
                                if hasattr(existing, "parent_rev"):
                                    existing.parent_rev = parent_rev
                                if hasattr(existing, "child_rev"):
                                    existing.child_rev = child_rev
                                if hasattr(existing, "occurrences"):
                                    existing.occurrences = occs
                                existing.updated_at = datetime.utcnow()
                                existing.save()
                            else:
                                kwargs = dict(parent_pn=parent_pn, child_pn=child_pn, qty=qty, uom="EA")
                                if "parent_rev" in BOMLink._fields:
                                    kwargs["parent_rev"] = parent_rev
                                if "child_rev" in BOMLink._fields:
                                    kwargs["child_rev"] = child_rev
                                if "occurrences" in BOMLink._fields:
                                    kwargs["occurrences"] = occs
                                BOMLink(**kwargs).save()
                                created_links += 1
                        except Exception as exc:
                            _report_issue(
                                report,
                                "error",
                                stage="links.save",
                                file=tree_name,
                                part_number=parent_pn,
                                message=f"Failed to save BOM link {parent_pn} -> {child_pn}.",
                                exc=exc,
                            )
                _stage_end(report, "links.save", links_save_start)

                if parent_pairs:
                    try:
                        dedupe_start = _stage_start()
                        removed_links += _dedupe_links_for_parents(parent_pairs)
                        _stage_end(report, "links.dedupe", dedupe_start)
                    except Exception as exc:
                        _report_issue(
                            report,
                            "error",
                            stage="links.dedupe",
                            message="Failed to dedupe BOM links for parents.",
                            exc=exc,
                        )

                if existing_parent_pairs:
                    bom_after = _children_from_links(links)
                    for parent_key in sorted(existing_parent_pairs):
                        diff = _diff_bom_children(
                            bom_before.get(parent_key, {}),
                            bom_after.get(parent_key, {}),
                        )
                        if diff:
                            entry = _ensure_modified_part(modified_parts, parent_key[0], parent_key[1])
                            entry["bom_changes"] = diff

            # 3) Discover and register artifacts for all parts (best effort)
            for pn, rev in tree_parts:
                key = (pn, rev)
                if key not in part_props:
                    part_props[key] = {
                        "part_number": pn,
                        "description": "",
                        "category": "",
                        "uom": "EA",
                        "revision": rev,
                        "attrs": {"seed": seed_tag},
                    }

            artifact_inserts = 0
            artifacts_found_by_type = defaultdict(int)
            seen: Set[Tuple[str, str]] = set()
            if scan_artifacts:
                artifacts_total_start = _stage_start()
                with timed_span("import.bom.artifacts"):
                    for _key, norm in part_props.items():
                        pn = _norm_pn(norm.get("part_number") or "")
                        rev = clean_rev(norm.get("revision") or "")
                        key = (pn, rev)
                        if not pn or key in seen:
                            continue
                        seen.add(key)

                        try:
                            part_doc = Part.objects(part_number__iexact=pn, revision__iexact=rev).only("attrs").first()
                            found = discover_part_files(
                                pn,
                                rev,
                                approved=bool(approved_value(harvest_part_attrs(part_doc))) if part_doc else None,
                            )
                        except Exception as exc:
                            _report_issue(
                                report,
                                "warning",
                                stage="artifacts.scan",
                                part_number=pn,
                                message="Failed to discover part files.",
                                exc=exc,
                            )
                            continue

                        recs = []
                        try:
                            for (group, is_dwg), meta in (found or {}).items():
                                rec = dict(meta)
                                rec["ext_group"] = group
                                rec["is_dwg"] = bool(is_dwg)
                                recs.append(rec)
                                artifacts_found_by_type[str(group or "unknown")] += 1
                        except Exception:
                            pass

                        try:
                            upsert_result = upsert_part_files_detailed(recs, pn, (rev or ""))
                            artifact_inserts += int(upsert_result.get("count") or 0)
                            if part_existed_before.get(key):
                                file_changes = list(upsert_result.get("changes") or [])
                                if file_changes:
                                    entry = _ensure_modified_part(modified_parts, pn, rev)
                                    for item in file_changes:
                                        file_change = dict(item)
                                        file_change["kind"] = "artifact"
                                        entry["file_changes"].append(file_change)
                        except Exception as exc:
                            _report_issue(
                                report,
                                "warning",
                                stage="artifacts.upsert",
                                part_number=pn,
                                message="Failed to upsert discovered part files.",
                                exc=exc,
                            )
                _stage_end(report, "artifacts.total", artifacts_total_start)

            thumbs = 0
            if generate_thumbs:
                thumbs_start = _stage_start()
                with timed_span("import.bom.thumbnails"):
                    try:
                        thumbs = generate_thumbs_for_parts(seen)
                    except Exception as exc:
                        thumbs = 0
                        _report_issue(
                            report,
                            "warning",
                            stage="thumbnails",
                            message="Failed to generate thumbnails.",
                            exc=exc,
                        )
                _stage_end(report, "thumbnails", thumbs_start)

            # root guess for convenience (top item in TREEBOM)
            root_pn = None
            root_rev = ""
            if tree_name:
                try:
                    txt = zf.read(tree_name).decode("utf-8-sig", errors="replace")
                    for line in txt.splitlines():
                        cols = line.split("\t")
                        if len(cols) >= 2 and cols[0].strip() not in ("", "ITEM NO."):
                            if cols[0].strip() == "1":
                                root_pn = _base_pn(cols[1].strip())
                            break
                except Exception:
                    root_pn = None

            if root_pn:
                try:
                    for (pn, rev), _norm in part_props.items():
                        if pn == root_pn:
                            if rev:
                                root_rev = clean_rev(rev)
                                break
                            if not root_rev:
                                root_rev = clean_rev(rev or "")
                except Exception:
                    root_rev = ""

            modified_parts_list: List[Dict[str, Any]] = []
            for key in sorted(modified_parts):
                entry = dict(modified_parts[key])
                entry["data_changes"] = list(entry.get("data_changes") or [])
                entry["file_changes"] = list(entry.get("file_changes") or [])
                if not entry["data_changes"] and not entry.get("bom_changes") and not entry["file_changes"]:
                    continue
                modified_parts_list.append(entry)

            report.update(
                {
                    "root": root_pn,
                    "root_revision": root_rev,
                    "parts_created": created_parts,
                    "parts_updated": updated_parts,
                    "modified_parts_count": len(modified_parts_list),
                    "modified_parts": modified_parts_list,
                    "links_created": created_links,
                    "links_skipped": skipped_links,
                    "links_removed": removed_links,
                    "parts_seeded": len(seeded_parts),
                    "parts_seeded_list": [{"part_number": pn, "revision": rev} for pn, rev in sorted(seeded_parts)],
                    "parts_with_props": len(part_props),
                    "artifacts_added": artifact_inserts,
                    "artifacts_found_by_type": dict(sorted(artifacts_found_by_type.items())),
                    "thumbnails_built": thumbs,
                    "thumbnails_generated": thumbs,
                }
            )

    report["resources_end"] = _snapshot_resources()
    _stage_end(report, "total", total_start)
    return report
