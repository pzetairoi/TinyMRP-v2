from __future__ import annotations

import ast
import io
import json
import os
import re
import shutil
import time
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Tuple

from flask import current_app

from app.models.extra_file import PartExtraFile
from app.models.part import Part
from app.services.import_zip import import_bom_zip
from app.services.filescan import upsert_part_files_detailed
from app.services.thumbs_gen import generate_thumbs_for_parts
from app.services.part_norm import clean_pn, clean_rev
from app.services.extra_files import (
    REV_EMPTY_TOKEN,
    extra_abs_path,
    extra_rel_path,
    extra_root,
    ensure_dir,
    guess_mime,
    hash_file,
    rev_from_token,
)


_DELIVERABLE_GROUPS = {
    "png",
    "pdf",
    "dxf",
    "step",
    "edr",
    "3mf",
    "ply",
    "stl",
    "datasheet",
}

_PART_OVERRIDE_MODE_DEFAULT = "unless_existing_approved"


def _stage_start() -> Tuple[float, float]:
    return (time.perf_counter(), time.process_time())


def _stage_end(timings: Dict[str, Any], name: str, start: Tuple[float, float]) -> None:
    if not name:
        return
    try:
        t0, c0 = start
        t1 = time.perf_counter()
        c1 = time.process_time()
        elapsed = float(t1 - t0)
        cpu = float(c1 - c0)
        idle = float(max(0.0, elapsed - cpu))
        timings[name] = {"elapsed_s": elapsed, "cpu_s": cpu, "idle_s": idle}
    except Exception:
        pass


def _snapshot_resources() -> Dict[str, Any]:
    snap: Dict[str, Any] = {
        "utc": datetime.utcnow().isoformat(),
        "cpu_s": float(time.process_time()),
    }
    try:
        import psutil  # type: ignore

        snap["rss_bytes"] = int(psutil.Process().memory_info().rss)
    except Exception:
        snap["rss_bytes"] = None
    return snap


def _try_parse_pn_rev_from_deliverable_filename(filename_only: str) -> Tuple[str, str, bool] | None:
    """
    Parse <PN>_REV_<REV> from a deliverable filename. Handles optional _DWG suffix for PNG drawing images.
    Returns (pn, rev, is_dwg).
    """
    name = os.path.basename(filename_only or "")
    if not name:
        return None
    base, _ext = os.path.splitext(name)
    if not base:
        return None

    is_dwg = False
    if base.upper().endswith("_DWG"):
        is_dwg = True
        base = base[:-4]
    idx = base.upper().rfind("_REV_")
    if idx <= 0:
        return None
    pn_raw = base[:idx]
    rev_raw = base[idx + 5 :]
    pn = clean_pn(pn_raw)
    rev = clean_rev(rev_raw)
    if not pn:
        return None
    return pn, rev, is_dwg

_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def _safe_zip_name(name: str) -> Optional[str]:
    if not name:
        return None
    if "\x00" in name:
        return None
    name = name.replace("\\", "/").lstrip("/")
    if not name:
        return None
    norm = os.path.normpath(name).replace("\\", "/")
    if norm in ("", ".", "/"):
        return None
    if norm.startswith("../") or norm == "..":
        return None
    if _DRIVE_RE.match(norm):
        return None
    return norm


def _base_pn(pn: str) -> str:
    if not pn:
        return ""
    return clean_pn(str(pn).split("^", 1)[0])


def _existing_part_pairs(pairs: set[Tuple[str, str]]) -> set[Tuple[str, str]]:
    existing: set[Tuple[str, str]] = set()
    for pn, rev in pairs:
        pn_clean = _base_pn(pn)
        rev_clean = clean_rev(rev)
        if not pn_clean:
            continue
        if Part.objects(part_number=pn_clean, revision=rev_clean).only("id").first() is not None:
            existing.add((pn_clean, rev_clean))
    return existing


def _ensure_modified_part_entry(report: Dict[str, Any], pn: str, rev: str) -> Dict[str, Any]:
    pn_clean = _base_pn(pn)
    rev_clean = clean_rev(rev)
    items = report.get("modified_parts")
    if not isinstance(items, list):
        items = []
        report["modified_parts"] = items
    for item in items:
        if (
            str(item.get("part_number") or "") == pn_clean
            and str(item.get("revision") or "") == rev_clean
        ):
            item.setdefault("data_changes", [])
            item.setdefault("bom_changes", None)
            item.setdefault("file_changes", [])
            return item
    entry = {
        "part_number": pn_clean,
        "revision": rev_clean,
        "data_changes": [],
        "bom_changes": None,
        "file_changes": [],
    }
    items.append(entry)
    return entry


def _parse_flatbom(
    txt: str,
    source_name: str = "",
    max_warnings: int = 3,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    failures = 0
    logger = None
    try:
        logger = current_app.logger
    except Exception:
        logger = None

    txt = (txt or "").lstrip("\ufeff")
    for raw in (txt or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        line = line.lstrip("\ufeff")
        cleaned = line.replace("...", "")
        try:
            d = None
            try:
                d = json.loads(cleaned)
            except Exception:
                d = ast.literal_eval(cleaned)
            if isinstance(d, dict):
                out.append(d)
        except Exception:
            if logger and failures < max_warnings:
                preview = line.replace("\t", " ")
                preview = preview[:80]
                label = source_name or "FLATBOM"
                logger.warning("FLATBOM parse failed (%s): %s", label, preview)
            failures += 1
            continue
    return out


def _build_bom_rev_map(z: zipfile.ZipFile) -> Tuple[Dict[str, str], List[Tuple[str, str]]]:
    flat_name = next(
        (n for n in z.namelist() if n.endswith("_FLATBOM.txt") and not n.endswith("/")),
        None,
    )
    if not flat_name:
        return {}, []
    try:
        flat_txt = z.read(flat_name).decode("utf-8-sig", errors="replace")
    except Exception:
        return {}, []
    bom_map: Dict[str, str] = {}
    pairs: List[Tuple[str, str]] = []
    for row in _parse_flatbom(flat_txt, source_name=flat_name):
        pn = _base_pn(row.get("partnumber") or row.get("part_number") or row.get("pn") or "")
        rev = clean_rev(row.get("revision") or row.get("rev") or "")
        if not pn:
            continue
        bom_map[pn] = rev
        pairs.append((pn, rev))
    return bom_map, pairs


def _load_extra_manifest(z: zipfile.ZipFile) -> Dict[Tuple[str, str, str], Dict[str, str]]:
    manifest_names = ("extra/_manifest.json", "extra/manifest.json")
    name = next((n for n in manifest_names if n in z.namelist()), None)
    if not name:
        return {}
    try:
        raw = z.read(name)
        data = json.loads(raw.decode("utf-8-sig", errors="replace") or "{}")
    except Exception:
        return {}
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, list):
        return {}
    out: Dict[Tuple[str, str, str], Dict[str, str]] = {}
    for item in files:
        if not isinstance(item, dict):
            continue
        pn = _base_pn(item.get("pn") or "")
        if not pn:
            continue
        rev = clean_rev(rev_from_token(item.get("rev") or ""))
        name = os.path.basename(item.get("name") or item.get("file") or "") or ""
        if not name:
            continue
        key = (pn.casefold(), rev.casefold(), name.casefold())
        out[key] = {
            "label": (item.get("label") or "").strip(),
            "ext": (item.get("ext") or item.get("extension") or "").strip(),
        }
    return out


def _allowed_path(abs_path: str, base_root: str) -> bool:
    try:
        ap = os.path.abspath(abs_path)
        base = os.path.abspath(base_root)
        ap_norm, base_norm = os.path.normcase(ap), os.path.normcase(base)
        try:
            return os.path.commonpath([ap_norm, base_norm]) == base_norm
        except Exception:
            return ap_norm.startswith(base_norm)
    except Exception:
        return False


def _write_zip_entry(z: zipfile.ZipFile, info: zipfile.ZipInfo, dest: str) -> None:
    ensure_dir(os.path.dirname(dest))
    with z.open(info, "r") as src, open(dest, "wb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)


def import_upload_pack(
    file_bytes: bytes,
    filename: str,
    *,
    uploaded_by: str = "",
    dry_run: bool = False,
    strict_structure: bool = False,
    allow_extra: bool = True,
    seed_tag: str = "upload-pack",
    override_mode: str = _PART_OVERRIDE_MODE_DEFAULT,
) -> Dict[str, Any]:
    timings: Dict[str, Any] = {}
    resources_start = _snapshot_resources()
    total_start = _stage_start()

    cfg = current_app.config
    max_zip_mb = int(cfg.get("UPLOAD_PACK_MAX_ZIP_MB") or 0)
    max_file_mb = int(cfg.get("UPLOAD_PACK_MAX_FILE_MB") or 0)
    max_files = int(cfg.get("UPLOAD_PACK_MAX_FILES") or 0)
    file_root = (cfg.get("FILE_ROOT_LOCAL") or cfg.get("FILES_LOCAL_ROOT") or "").strip()
    if not file_root:
        raise ValueError("FILE_ROOT_LOCAL not configured")

    if max_zip_mb and len(file_bytes) > max_zip_mb * 1024 * 1024:
        raise ValueError("ZIP exceeds configured size limit")

    warnings: List[str] = []
    pair_warnings: Dict[Tuple[str, str], List[str]] = {}
    extra_counts: Dict[Tuple[str, str], int] = {}
    extra_pairs: set[Tuple[str, str]] = set()
    extra_file_changes: List[Dict[str, Any]] = []

    deliverables_written = 0
    extras_written = 0
    deliverable_artifact_recs: List[Dict[str, Any]] = []
    deliverable_pairs: set[Tuple[str, str]] = set()

    zip_open_start = _stage_start()
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        _stage_end(timings, "zip.open", zip_open_start)
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if max_files and len(infos) > max_files:
            raise ValueError("ZIP exceeds configured file count limit")

        bom_map_start = _stage_start()
        bom_map, bom_pairs_list = _build_bom_rev_map(zf)
        _stage_end(timings, "bom.rev_map", bom_map_start)
        bom_pairs = set(bom_pairs_list)
        if not bom_pairs:
            warnings.append("BOM files not found in ZIP.")

        flat_name = next((n for n in zf.namelist() if n.endswith("_FLATBOM.txt")), None)
        tree_name = next((n for n in zf.namelist() if n.endswith("_TREEBOM.txt")), None)
        bom_names = set()
        if flat_name:
            bom_names.add(_safe_zip_name(flat_name) or flat_name)
        if tree_name:
            bom_names.add(_safe_zip_name(tree_name) or tree_name)
        extra_manifest = _load_extra_manifest(zf)
        extra_manifest_names = {"extra/_manifest.json", "extra/manifest.json"}

        scan_entries_start = _stage_start()
        for info in infos:
            if max_file_mb and info.file_size > max_file_mb * 1024 * 1024:
                raise ValueError(f"ZIP entry too large: {info.filename}")

            safe_name = _safe_zip_name(info.filename)
            if not safe_name:
                raise ValueError(f"Unsafe ZIP entry blocked: {info.filename}")

            if safe_name in extra_manifest_names:
                continue
            if safe_name in bom_names or safe_name.endswith("_FLATBOM.txt") or safe_name.endswith("_TREEBOM.txt"):
                continue

            parts = safe_name.split("/")
            if not parts:
                continue
            head = parts[0].lower()

            if head in ("bom",):
                continue

            if head == "deliverables" or head in _DELIVERABLE_GROUPS:
                if head == "deliverables":
                    if len(parts) < 3:
                        msg = f"Deliverables entry missing group: {safe_name}"
                        if strict_structure:
                            raise ValueError(msg)
                        warnings.append(msg)
                        continue
                    group = parts[1].lower()
                    rel_parts = parts[2:]
                else:
                    group = head
                    rel_parts = parts[1:]

                if group not in _DELIVERABLE_GROUPS:
                    msg = f"Unknown deliverables group: {group}"
                    if strict_structure:
                        raise ValueError(msg)
                    warnings.append(msg)
                    continue
                if not rel_parts:
                    msg = f"Deliverables entry missing filename: {safe_name}"
                    if strict_structure:
                        raise ValueError(msg)
                    warnings.append(msg)
                    continue
                filename_only = os.path.basename(rel_parts[-1])
                if len(rel_parts) > 1:
                    warnings.append(f"Nested deliverables path flattened: {safe_name}")

                dest_rel = f"{group}/{filename_only}"
                dest_abs = os.path.abspath(os.path.join(file_root, dest_rel))
                if not _allowed_path(dest_abs, file_root):
                    msg = f"Blocked deliverables path: {safe_name}"
                    if strict_structure:
                        raise ValueError(msg)
                    warnings.append(msg)
                    continue
                if not dry_run:
                    _write_zip_entry(zf, info, dest_abs)
                    try:
                        parsed = _try_parse_pn_rev_from_deliverable_filename(filename_only)
                        if parsed:
                            pn_parsed, rev_parsed, is_dwg = parsed
                            ext = os.path.splitext(filename_only)[1].lstrip(".").lower()
                            if ext:
                                deliverable_pairs.add((pn_parsed, rev_parsed))
                                deliverable_artifact_recs.append(
                                    {
                                        "part_number": pn_parsed,
                                        "revision": rev_parsed,
                                        "ext_group": group,
                                        "ext": ext,
                                        "rel_path": dest_rel,
                                        "is_dwg": bool(is_dwg) if group == "png" else False,
                                        "mtime_iso": datetime.utcnow(),
                                        "size": float(os.path.getsize(dest_abs)),
                                    }
                                )
                    except Exception:
                        pass
                deliverables_written += 1
                continue

            if head == "extra":
                if not allow_extra:
                    warnings.append("Extra files disabled by configuration.")
                    continue
                if len(parts) < 3:
                    msg = f"Extra entry missing PN: {safe_name}"
                    if strict_structure:
                        raise ValueError(msg)
                    warnings.append(msg)
                    continue
                pn_raw = parts[1]
                pn = _base_pn(pn_raw)
                if not pn:
                    msg = f"Extra entry has empty PN: {safe_name}"
                    if strict_structure:
                        raise ValueError(msg)
                    warnings.append(msg)
                    continue
                if len(parts) >= 4:
                    rev_token = parts[2]
                    rel_parts = parts[3:]
                    legacy = False
                else:
                    rev_token = ""
                    rel_parts = parts[2:]
                    legacy = True
                if not rel_parts:
                    msg = f"Extra entry missing filename: {safe_name}"
                    if strict_structure:
                        raise ValueError(msg)
                    warnings.append(msg)
                    continue

                rev = clean_rev(rev_from_token(rev_token))
                if legacy:
                    mapped = bom_map.get(pn)
                    if mapped is None:
                        msg = f"Extra entry missing rev for {pn}; using empty rev."
                        warnings.append(msg)
                        pair_warnings.setdefault((pn, ""), []).append(msg)
                    rev = clean_rev(mapped or "")
                if rev_token == REV_EMPTY_TOKEN:
                    rev = ""

                file_name = rel_parts[-1]
                subpath = "/".join(rel_parts[:-1])
                rel_path = extra_rel_path(pn, rev, file_name, subpath=subpath)
                abs_path = extra_abs_path(rel_path)
                base_root = extra_root()
                if not base_root or not _allowed_path(abs_path, base_root):
                    msg = f"Blocked extra path: {safe_name}"
                    if strict_structure:
                        raise ValueError(msg)
                    warnings.append(msg)
                    continue
                label_key = (pn.casefold(), rev.casefold(), os.path.basename(file_name).casefold())
                label = ""
                meta = extra_manifest.get(label_key)
                if meta:
                    label = (meta.get("label") or "").strip()

                if not dry_run:
                    _write_zip_entry(zf, info, abs_path)
                    size = float(os.path.getsize(abs_path))
                    mime = guess_mime(abs_path)
                    sha = hash_file(abs_path)
                    existing = PartExtraFile.objects(
                        part_number=pn,
                        revision=rev,
                        rel_path=rel_path,
                    ).first()
                    extra_action = "updated" if existing else "added"
                    if existing:
                        existing.original_name = os.path.basename(file_name)
                        existing.size = size
                        existing.mime = mime
                        existing.sha256 = sha
                        if label:
                            existing.label = label
                        existing.uploaded_by = uploaded_by or existing.uploaded_by
                        existing.uploaded_at = datetime.utcnow()
                        existing.source = seed_tag
                        existing.save()
                    else:
                        PartExtraFile(
                            part_number=pn,
                            revision=rev,
                            original_name=os.path.basename(file_name),
                            rel_path=rel_path,
                            size=size,
                            mime=mime,
                            sha256=sha,
                            label=label,
                            uploaded_by=uploaded_by,
                            uploaded_at=datetime.utcnow(),
                            source=seed_tag,
                        ).save()
                    extra_file_changes.append(
                        {
                            "part_number": pn,
                            "revision": rev,
                            "kind": "extra_file",
                            "action": extra_action,
                            "name": os.path.basename(file_name),
                            "rel_path": rel_path,
                            "label": label,
                        }
                    )
                extras_written += 1
                extra_pairs.add((pn, rev))
                extra_counts[(pn, rev)] = extra_counts.get((pn, rev), 0) + 1
                continue

            msg = f"Unknown ZIP entry: {safe_name}"
            if strict_structure:
                raise ValueError(msg)
            warnings.append(msg)
        _stage_end(timings, "zip.entries", scan_entries_start)

    bom_result = None
    preexisting_part_pairs = _existing_part_pairs(set(bom_pairs) | set(deliverable_pairs) | set(extra_pairs))
    if not dry_run:
        bom_start = _stage_start()
        # If the ZIP has no deliverables (or we couldn't parse any deliverable filenames into PN/REV),
        # fall back to scanning storage so BOM-only uploads still register all available files.
        scan_storage = len(deliverable_artifact_recs) == 0
        bom_result = import_bom_zip(
            file_bytes,
            filename,
            seed_tag=seed_tag,
            scan_artifacts=scan_storage,
            generate_thumbs=scan_storage,
            override_mode=override_mode,
        )
        _stage_end(timings, "bom.import", bom_start)

        # Upsert deliverable artifacts directly (avoid expensive filesystem scan during BOM import).
        artifacts_upserted = 0
        thumbs = 0
        artifacts_found_by_type: Dict[str, int] = {}
        deliverable_file_changes: List[Dict[str, Any]] = []
        artifacts_start = _stage_start()
        try:
            upsert_result = upsert_part_files_detailed(deliverable_artifact_recs)
            artifacts_upserted = int(upsert_result.get("count") or 0)
            for rec in list(upsert_result.get("changes") or []):
                item = dict(rec)
                item["kind"] = "deliverable"
                item["name"] = os.path.basename(str(item.get("rel_path") or ""))
                deliverable_file_changes.append(item)
            for rec in deliverable_artifact_recs:
                grp = str(rec.get("ext_group") or "unknown")
                artifacts_found_by_type[grp] = artifacts_found_by_type.get(grp, 0) + 1
        except Exception:
            artifacts_upserted = 0
        try:
            thumbs = generate_thumbs_for_parts(list(deliverable_pairs))
        except Exception:
            thumbs = 0
        _stage_end(timings, "artifacts.upsert", artifacts_start)

        if isinstance(bom_result, dict):
            # Preserve existing report keys expected by UI/tests.
            bom_result["artifacts_added"] = int(bom_result.get("artifacts_added") or 0) + int(artifacts_upserted)
            bom_result["artifacts_found_by_type"] = artifacts_found_by_type or (bom_result.get("artifacts_found_by_type") or {})
            bom_result["thumbnails_generated"] = int(bom_result.get("thumbnails_generated") or 0) + int(thumbs)
            bom_result["thumbnails_built"] = int(bom_result.get("thumbnails_built") or 0) + int(thumbs)
            combined_file_changes = list(deliverable_file_changes) + list(extra_file_changes)
            for change in combined_file_changes:
                key = (_base_pn(change.get("part_number") or ""), clean_rev(change.get("revision") or ""))
                if key not in preexisting_part_pairs:
                    continue
                entry = _ensure_modified_part_entry(bom_result, key[0], key[1])
                entry.setdefault("file_changes", []).append(change)
            bom_result["modified_parts"] = sorted(
                list(bom_result.get("modified_parts") or []),
                key=lambda item: (str(item.get("part_number") or ""), str(item.get("revision") or "")),
            )
            bom_result["modified_parts_count"] = len(bom_result["modified_parts"])

    items: List[Dict[str, Any]] = []
    pairs = set(bom_pairs) | set(extra_pairs)
    for pn, rev in sorted(pairs, key=lambda t: (t[0], t[1])):
        items.append(
            {
                "pn": pn,
                "rev": rev,
                "imported": bool(bom_result) and (pn, rev) in bom_pairs,
                "extra_files_added": extra_counts.get((pn, rev), 0),
                "warnings": pair_warnings.get((pn, rev), []),
            }
        )

    _stage_end(timings, "total", total_start)
    return {
        "zip": filename,
        "dry_run": bool(dry_run),
        "override_mode": override_mode,
        "items": items,
        "warnings": warnings,
        "deliverables_written": deliverables_written,
        "extra_files_written": extras_written,
        "import": bom_result,
        "timings": timings,
        "resources_start": resources_start,
        "resources_end": _snapshot_resources(),
    }
