# app/services/filescan.py — discovery + PartFile registry sync (upsert & stale removal)
import os, re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Dict, List, Tuple, Any, Optional
from urllib.parse import urlsplit

from flask import current_app
from app.models.artifact import PartFile
from app.services.app_settings import resolve_file_sources
from app.services.canonical_fields import canonical_attr_key
from app.services.timezone_utils import utc_now

_DATASHEET_ATTR_KEYS = {
    "datasheet",
    "oem_data_sheet",
    "oem_datasheet",
    "data_sheet",
    "datasheet_url",
}
_DATASHEET_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

def _sources(approved: Optional[bool] = None) -> List[Dict[str, Any]]:
    try:
        configured = current_app.config.get("FILE_SOURCES")
        if isinstance(configured, list) and configured:
            sources = [dict(item) for item in configured if isinstance(item, dict)]
        else:
            sources = resolve_file_sources()
    except Exception:
        sources = []
    active = [src for src in sources if str(src.get("local_root") or "").strip()]
    if approved is None:
        return active
    pref_key = "use_for_approved" if approved else "use_for_unapproved"
    preferred = [src for src in active if bool(src.get(pref_key, True))]
    fallback = [src for src in active if src not in preferred]
    return preferred + fallback

def _expectations_for(pn: str, rev: str) -> List[Tuple[str, str, bool]]:
    """
    Return list of expected (ext_group, suffix, is_dwg).
    We only special-case PNG:
      - normal preview: {base}.png
      - drawing screenshot: {base}_DWG.png
    """
    # Build candidate basenames in multiple case variants to be robust
    # against filename capitalization differences.
    rev_str = (rev or "")
    base_upper = f"{pn.upper()}_REV_{rev_str.upper()}" if rev_str else f"{pn.upper()}_REV_"
    base_raw   = f"{pn}_REV_{rev_str}" if rev is not None else f"{pn}_REV_"

    # Also consider variant without the _REV_ segment when revision is empty.
    base_no_rev_upper = pn.upper()
    base_no_rev_raw   = pn

    wants: List[Tuple[str, str, bool]] = []
    # png - preview (multiple candidates)
    for b in (base_upper, base_raw) + ((base_no_rev_upper, base_no_rev_raw) if not rev_str else ()):  # type: ignore
        wants.append(("png",  f"{b}.png", False))
        # png - drawing screen
        wants.append(("png",  f"{b}_DWG.png", True))
    # others (one-per-extension)
    for grp, exts in [
        ("pdf",  ("pdf",)),
        ("dxf",  ("dxf",)),
        ("step", ("step","stp")),
        ("edr",  ("edr","eprt","easm","EDR","EPRT","EASM")),
        ("3mf",  ("3mf",)),
        ("ply",  ("ply",)),
        ("stl",  ("stl",)),
        ("datasheet", ("pdf","jpg","jpeg","png")),
    ]:
        # store exactly one file per ext_group -> we’ll accept any of these concrete exts
        # filename is still strictly base + "." + ext (no _DWG here)
        for ext in exts:
            for b in (base_upper, base_raw) + ((base_no_rev_upper, base_no_rev_raw) if not rev_str else ()):  # type: ignore
                wants.append((grp, f"{b}.{ext}", False))
    return wants

def _find_case_insensitive(local_root: Path, rel: str) -> Path | None:
    """
    Try to find file 'rel' under local_root, case-insensitive for both dirs and filename.
    """
    parts = Path(rel).parts
    cur = local_root
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            # filename: select first matching ignoring case
            try:
                # if exact exists
                p = cur / part
                if p.exists():
                    return p
            except Exception:
                pass
            low = part.lower()
            for cand in cur.iterdir():
                if cand.name.lower() == low and cand.is_file():
                    return cand
            return None
        else:
            # directory level
            nextd = cur / part
            if nextd.exists() and nextd.is_dir():
                cur = nextd
            else:
                low = part.lower()
                found = None
                for d in cur.iterdir():
                    if d.is_dir() and d.name.lower() == low:
                        found = d
                        break
                if not found:
                    return None
                cur = found
    return None

def _rel_path_for(candidate: Path, local_root: Path) -> str:
    
    return str(candidate.relative_to(local_root)).replace("\\","/")

def _is_http_url(value: str) -> bool:
    try:
        parsed = urlsplit(str(value or "").strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _datasheet_attr_values(attrs: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(attrs, dict):
        return []
    out: List[str] = []
    seen: set[str] = set()
    for raw_key, raw_value in attrs.items():
        if canonical_attr_key(raw_key) not in _DATASHEET_ATTR_KEYS:
            continue
        values = raw_value if isinstance(raw_value, (list, tuple, set)) else [raw_value]
        for item in values:
            text = str(item or "").strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(text)
    return out


def datasheet_url_from_attrs(attrs: Optional[Dict[str, Any]]) -> Optional[str]:
    for value in _datasheet_attr_values(attrs):
        if _is_http_url(value):
            return value
    return None


def datasheet_attr_present(attrs: Optional[Dict[str, Any]]) -> bool:
    return bool(_datasheet_attr_values(attrs))


def _safe_datasheet_rel(value: str) -> Optional[str]:
    text = str(value or "").strip().replace("\\", "/")
    if not text or _is_http_url(text):
        return None
    if text.startswith("/") or re.match(r"^[A-Za-z]:/", text):
        return None
    parts = [part for part in PurePosixPath(text).parts if part not in ("", ".")]
    if not parts or parts[0].lower() != "datasheet" or any(part == ".." for part in parts):
        return None
    if Path(parts[-1]).suffix.lower() not in _DATASHEET_EXTENSIONS:
        return None
    return "/".join(parts)


def _datasheet_rel_candidates(attrs: Optional[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for value in _datasheet_attr_values(attrs):
        if _is_http_url(value):
            continue
        basename = os.path.basename(str(value or "").replace("\\", "/").rstrip("/\\"))
        ext = Path(basename).suffix.lower()
        safe_rel = _safe_datasheet_rel(value)
        candidates = []
        if safe_rel:
            candidates.append(safe_rel)
        if basename and ext in _DATASHEET_EXTENSIONS:
            candidates.append(f"datasheet/{basename}")
        for candidate in candidates:
            token = candidate.casefold()
            if token in seen:
                continue
            seen.add(token)
            out.append(candidate)
    return out


def _build_record(
    p: Path,
    local_root: Path,
    http: str,
    source: Dict[str, Any],
    source_rank: int,
    *,
    is_dwg: bool,
    match_priority: int = 1,
) -> Dict[str, Any]:
    try:
        resolved_root = local_root.resolve(strict=False)
        resolved_file = p.resolve(strict=True)
        resolved_file.relative_to(resolved_root)
        if not resolved_file.is_file():
            raise ValueError("not a regular file")
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError("discovered file is outside its storage root") from exc
    stat = p.stat()
    rel_path = _rel_path_for(p, local_root)
    return {
        "ext": p.suffix.lstrip("."),
        "rel_path": rel_path,
        "abs_path": str(p),
        "http_url": (http.rstrip("/") + "/" + rel_path) if http else None,
        "size": float(stat.st_size),
        "mtime_iso": datetime.fromtimestamp(stat.st_mtime),
        "is_dwg": is_dwg,
        "source": str(source.get("id") or "scan"),
        "meta_info": {
            "source_id": str(source.get("id") or ""),
            "source_label": str(source.get("label") or ""),
            "source_root": str(source.get("local_root") or ""),
            "source_priority": int(source.get("priority") or (source_rank + 1)),
        },
        "_source_rank": source_rank,
        "_match_priority": match_priority,
    }


def _prefer_record(prev: Optional[Dict[str, Any]], record: Dict[str, Any]) -> bool:
    if prev is None:
        return True
    prev_match = int(prev.get("_match_priority", 1))
    new_match = int(record.get("_match_priority", 1))
    if new_match < prev_match:
        return True
    if new_match > prev_match:
        return False
    prev_rank = int(prev.get("_source_rank", 10**6))
    new_rank = int(record.get("_source_rank", 10**6))
    if new_rank < prev_rank:
        return True
    if new_rank > prev_rank:
        return False
    return prev["mtime_iso"] < record["mtime_iso"]


def discover_part_files(
    pn: str,
    rev: str,
    *,
    approved: Optional[bool] = None,
    attrs: Optional[Dict[str, Any]] = None,
) -> Dict[Tuple[str,bool], Dict]:
    """
    Return a dict keyed by (ext_group, is_dwg) -> record {ext, rel_path, http_url, size, mtime_iso}.
    When multiple sources contain the same artifact, source preference wins and mtime breaks ties inside
    the same source rank.
    """
    sources = _sources(approved)
    if not sources:
        return {}

    found: Dict[Tuple[str, bool], Dict[str, Any]] = {}
    datasheet_candidates = _datasheet_rel_candidates(attrs)
    for source_rank, source in enumerate(sources):
        local_root = Path(str(source.get("local_root") or "").strip())
        if not local_root:
            continue
        http = str(source.get("url_prefix") or "").strip()
        for candidate_rel in datasheet_candidates:
            p = _find_case_insensitive(local_root, candidate_rel)
            if not p:
                continue
            key = ("datasheet", False)
            record = _build_record(
                p,
                local_root,
                http,
                source,
                source_rank,
                is_dwg=False,
                match_priority=0,
            )
            if _prefer_record(found.get(key), record):
                found[key] = record

        for ext_group, leaf, is_dwg in _expectations_for(pn, rev):
            candidate_rel = f"{ext_group}/{leaf}"
            p = _find_case_insensitive(local_root, candidate_rel)
            if not p:
                continue
            key = (ext_group, is_dwg)
            record = _build_record(
                p,
                local_root,
                http,
                source,
                source_rank,
                is_dwg=is_dwg,
            )
            if _prefer_record(found.get(key), record):
                found[key] = record

    for record in found.values():
        record.pop("_source_rank", None)
        record.pop("_match_priority", None)
    return found


def _group_from_ext(ext: str) -> Optional[str]:
    ext = (ext or "").lower()
    if ext in {"png"}: return "png"
    if ext in {"pdf"}: return "pdf"
    if ext in {"dxf"}: return "dxf"
    if ext in {"step", "stp"}: return "step"
    if ext in {"eprt", "easm", "edrw"}: return "edr"
    if ext in {"3mf"}: return "3mf"
    if ext in {"ply"}: return "ply"
    if ext in {"stl"}: return "stl"
    return None


def upsert_part_files_detailed(
    recs: List[Dict[str, Any]],
    pn: Optional[str] = None,
    rev: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Upsert a batch of file records.
    - recs: list of dicts (each may include pn/part_number, rev/revision,
      ext_group/group, ext, rel_path, size, mtime_iso, http_url, is_dwg, etc.)
    - pn, rev: optional defaults applied to all records when missing.
    Returns a report with total upserts attempted and per-record changes.
    """
    n = 0
    changes: List[Dict[str, Any]] = []
    affected_pairs: set[tuple[str, str]] = set()
    for r in recs or []:
        rpn = pn or r.get("pn") or r.get("part_number")
        rrev = (rev if rev is not None else r.get("rev") or r.get("revision") or "")
        group = (r.get("ext_group") or r.get("group") or "").lower()
        ext = (r.get("ext") or "").lower()
        is_dwg = bool(r.get("is_dwg"))

        if not rpn or ext == "":
            # Not enough to identify the artifact; skip quietly
            continue

        # Unique key for your "one file per ext_group+ext per (pn,rev)" rule
        query = dict(part_number=rpn, revision=rrev, ext_group=group, ext=ext, is_dwg=is_dwg)
        existing = PartFile.objects(**query).first()

        # Allowed fields from the model
        allowed = set(PartFile._fields.keys())

        # Build atomic updates for modify()
        updates: Dict[str, Any] = {}
        final_values: Dict[str, Any] = {}

        # Normalized rel_path -> also use as unique, non-null `path`
        rel_path = r.get("rel_path") or ""
        norm_rel = rel_path.replace("\\", "/").lstrip("/")

        if "rel_path" in allowed and norm_rel:
            updates["set__rel_path"] = norm_rel
            final_values["rel_path"] = norm_rel

        abs_path = str(r.get("abs_path") or "").strip()
        if "path" in allowed and (abs_path or norm_rel):
            updates["set__path"] = abs_path or norm_rel
            final_values["path"] = abs_path or norm_rel

        # Pass through common metadata if present
        if "http_url" in r and "http_url" in allowed:
            updates["set__http_url"] = r["http_url"]
            final_values["http_url"] = r["http_url"]
        if "urls" in r and "urls" in allowed:
            updates["set__urls"] = r["urls"]
            final_values["urls"] = r["urls"]
        if "size" in r and "size" in allowed:
            updates["set__size"] = r["size"]
            final_values["size"] = r["size"]
        if "mtime_iso" in r and "mtime_iso" in allowed:
            updates["set__mtime_iso"] = r["mtime_iso"]
            final_values["mtime_iso"] = r["mtime_iso"]
        if "is_dwg" in r and "is_dwg" in allowed:
            updates["set__is_dwg"] = r["is_dwg"]
            final_values["is_dwg"] = r["is_dwg"]
        if "content_type" in r and "content_type" in allowed:
            updates["set__content_type"] = r["content_type"]
            final_values["content_type"] = r["content_type"]
        if "source" in r and "source" in allowed:
            updates["set__source"] = r["source"]
            final_values["source"] = r["source"]
        if "meta_info" in r and "meta_info" in allowed:
            updates["set__meta_info"] = r["meta_info"]
            final_values["meta_info"] = r["meta_info"]

        # Optional: stamp first discovery without touching on updates
        if "discovered_at" in allowed:
            updates.setdefault("set_on_insert__discovered_at", utc_now())

        # Safety: never send an empty update
        if not updates:
            continue

        action = "added" if existing is None else "updated"
        changed_fields: List[str] = []
        if existing is None:
            changed_fields = sorted(final_values.keys())
        else:
            for field_name, new_value in final_values.items():
                if getattr(existing, field_name, None) != new_value:
                    changed_fields.append(field_name)

        # Upsert
        PartFile.objects(**query).modify(upsert=True, new=True, **updates)  # type: ignore
        n += 1
        affected_pairs.add((str(rpn), str(rrev or "")))
        if action == "added" or changed_fields:
            changes.append(
                {
                    "part_number": str(rpn),
                    "revision": str(rrev or ""),
                    "ext_group": group,
                    "ext": ext,
                    "is_dwg": is_dwg,
                    "rel_path": norm_rel,
                    "action": action,
                    "changed_fields": changed_fields,
                }
            )

    materialized = {"scanned": 0, "updated": 0}
    if affected_pairs:
        from app.services.part_materialized import sync_materialized_fields_for_pairs

        materialized = sync_materialized_fields_for_pairs(affected_pairs)

    return {"count": n, "changes": changes, "materialized": materialized}


def upsert_part_files(
    recs: List[Dict[str, Any]],
    pn: Optional[str] = None,
    rev: Optional[str] = None,
) -> int:
    return int(upsert_part_files_detailed(recs, pn=pn, rev=rev).get("count") or 0)


def _part_file_on_disk(doc: PartFile, roots: List[Path]) -> bool:
    """
    Return True when the physical file backing a PartFile record still exists.
    Checks the stored absolute path first, then rel_path against every
    configured source root (case-insensitive, matching discovery behaviour).
    """
    try:
        from app.services.file_security import resolve_managed_path

        return resolve_managed_path(doc, must_exist=True).is_file()
    except Exception:
        return False


def _remove_thumb_file(doc: PartFile) -> None:
    """Best-effort removal of the generated thumbnail for a PartFile record."""
    try:
        thumb_rel = str(getattr(doc, "thumb_rel_path", "") or "").strip()
        if not thumb_rel:
            return
        root = (
            current_app.config.get("FILE_ROOT_LOCAL")
            or current_app.config.get("FILES_LOCAL_ROOT")
            or ""
        ).rstrip("/\\")
        if not root:
            return
        base = os.path.abspath(root)
        abs_thumb = os.path.abspath(os.path.join(base, thumb_rel.replace("/", os.sep)))
        if os.path.commonpath([os.path.normcase(abs_thumb), os.path.normcase(base)]) != os.path.normcase(base):
            return
        if os.path.isfile(abs_thumb):
            os.remove(abs_thumb)
    except Exception:
        pass


def remove_stale_part_files(
    pn: str,
    rev: str,
    found: Optional[Dict[Tuple[str, bool], Dict]] = None,
    *,
    allowed_ids: Optional[set[str]] = None,
) -> Dict[str, Any]:
    """
    Remove PartFile DB entries for (pn, rev) whose backing file no longer
    exists on disk.

    - found: optional result of discover_part_files(); any (ext_group, is_dwg)
      key present there was just (re)discovered and is always kept.
    - Records whose physical file still exists are kept even when not
      re-discovered (e.g. uploaded artifacts that don't match scan naming).
    - Safety: when no configured source root directory is reachable (storage
      offline / not mounted), nothing is removed.
    """
    pn_clean = (pn or "").strip()
    rev_clean = str(rev or "")
    if not pn_clean:
        return {"count": 0, "removed": []}

    roots: List[Path] = []
    for src in _sources(None):
        try:
            root = Path(str(src.get("local_root") or "").strip())
            if str(root) and root.is_dir():
                roots.append(root)
        except Exception:
            continue
    if not roots:
        # Storage unreachable -> do not treat files as deleted.
        return {"count": 0, "removed": [], "skipped": "no_reachable_source_roots"}

    found_keys = {
        (str(group or "").lower(), bool(is_dwg))
        for (group, is_dwg) in (found or {}).keys()
    }

    removed: List[Dict[str, Any]] = []
    for doc in PartFile.objects(part_number__iexact=pn_clean, revision__iexact=rev_clean):
        if allowed_ids is not None and str(doc.id) not in allowed_ids:
            continue
        key = ((doc.ext_group or "").lower(), bool(doc.is_dwg))
        if key in found_keys:
            continue
        if _part_file_on_disk(doc, roots):
            continue
        _remove_thumb_file(doc)
        removed.append(
            {
                "part_number": str(doc.part_number or ""),
                "revision": str(doc.revision or ""),
                "ext_group": str(doc.ext_group or ""),
                "ext": str(doc.ext or ""),
                "is_dwg": bool(doc.is_dwg),
                "rel_path": str(doc.rel_path or ""),
                "action": "removed",
            }
        )
        doc.delete()

    return {"count": len(removed), "removed": removed}


def plan_part_file_refresh(
    pn: str,
    rev: str,
    recs: List[Dict[str, Any]],
    found: Optional[Dict[Tuple[str, bool], Dict]] = None,
) -> Dict[str, Any]:
    """Classify all metadata effects without mutating database or storage."""

    additions = 0
    replacements = 0
    for record in recs:
        ext = str(record.get("ext") or "").strip().lower()
        group = str(record.get("ext_group") or "").strip().lower()
        if not ext:
            continue
        existing = PartFile.objects(
            part_number__iexact=pn,
            revision__iexact=rev,
            ext_group=group,
            ext=ext,
            is_dwg=bool(record.get("is_dwg")),
        ).first()
        if existing is None:
            additions += 1
        else:
            replacements += 1

    roots: List[Path] = []
    for source in _sources(None):
        try:
            root = Path(str(source.get("local_root") or "").strip())
            if str(root) and root.is_dir():
                roots.append(root)
        except Exception:
            continue
    stale_ids: list[str] = []
    if roots:
        found_keys = {
            (str(group or "").lower(), bool(is_dwg))
            for (group, is_dwg) in (found or {}).keys()
        }
        for doc in PartFile.objects(
            part_number__iexact=pn,
            revision__iexact=rev,
        ):
            key = ((doc.ext_group or "").lower(), bool(doc.is_dwg))
            if key in found_keys or _part_file_on_disk(doc, roots):
                continue
            stale_ids.append(str(doc.id))
    return {
        "additions": additions,
        "replacements": replacements,
        "stale_ids": stale_ids,
        "requires": frozenset(
            permission
            for permission, needed in (
                ("files.add", additions > 0),
                ("files.replace", replacements > 0),
                ("files.purge", bool(stale_ids)),
            )
            if needed
        ),
    }
