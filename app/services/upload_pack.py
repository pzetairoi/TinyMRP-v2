from __future__ import annotations

import ast
import io
import json
import os
import re
import shutil
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Tuple

from flask import current_app

from app.models.extra_file import PartExtraFile
from app.services.import_zip import import_bom_zip
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
) -> Dict[str, Any]:
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

    deliverables_written = 0
    extras_written = 0

    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if max_files and len(infos) > max_files:
            raise ValueError("ZIP exceeds configured file count limit")

        bom_map, bom_pairs_list = _build_bom_rev_map(zf)
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
                extras_written += 1
                extra_pairs.add((pn, rev))
                extra_counts[(pn, rev)] = extra_counts.get((pn, rev), 0) + 1
                continue

            msg = f"Unknown ZIP entry: {safe_name}"
            if strict_structure:
                raise ValueError(msg)
            warnings.append(msg)

    bom_result = None
    if not dry_run:
        bom_result = import_bom_zip(file_bytes, filename, seed_tag=seed_tag)

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

    return {
        "zip": filename,
        "dry_run": bool(dry_run),
        "items": items,
        "warnings": warnings,
        "deliverables_written": deliverables_written,
        "extra_files_written": extras_written,
        "import": bom_result,
    }
