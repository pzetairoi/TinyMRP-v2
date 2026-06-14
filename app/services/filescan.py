# app/services/filescan.py
import os, re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

from flask import current_app
from app.models.artifact import PartFile
from app.services.app_settings import resolve_file_sources

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

def discover_part_files(pn: str, rev: str, *, approved: Optional[bool] = None) -> Dict[Tuple[str,bool], Dict]:
    """
    Return a dict keyed by (ext_group, is_dwg) -> record {ext, rel_path, http_url, size, mtime_iso}.
    When multiple sources contain the same artifact, source preference wins and mtime breaks ties inside
    the same source rank.
    """
    sources = _sources(approved)
    if not sources:
        return {}

    found: Dict[Tuple[str, bool], Dict[str, Any]] = {}
    for source_rank, source in enumerate(sources):
        local_root = Path(str(source.get("local_root") or "").strip())
        if not local_root:
            continue
        http = str(source.get("url_prefix") or "").strip()
        for ext_group, leaf, is_dwg in _expectations_for(pn, rev):
            candidate_rel = f"{ext_group}/{leaf}"
            p = _find_case_insensitive(local_root, candidate_rel)
            if not p:
                continue
            stat = p.stat()
            key = (ext_group, is_dwg)
            rel_path = _rel_path_for(p, local_root)
            record: Dict[str, Any] = {
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
            }

            prev = found.get(key)
            if prev is None:
                found[key] = record
                continue
            prev_rank = int(prev.get("_source_rank", 10**6))
            if source_rank < prev_rank:
                found[key] = record
                continue
            if source_rank == prev_rank and prev["mtime_iso"] < record["mtime_iso"]:
                found[key] = record

    for record in found.values():
        record.pop("_source_rank", None)
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
            updates.setdefault("set_on_insert__discovered_at", datetime.utcnow())

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

    return {"count": n, "changes": changes}


def upsert_part_files(
    recs: List[Dict[str, Any]],
    pn: Optional[str] = None,
    rev: Optional[str] = None,
) -> int:
    return int(upsert_part_files_detailed(recs, pn=pn, rev=rev).get("count") or 0)
