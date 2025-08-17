import os, re, hashlib
from datetime import datetime, timezone
from typing import Dict, List, Iterable
from app.models.artifact import PartFile

# Folder names we scan (under each root) -> extension variants we accept
EXT_MAP: Dict[str, List[str]] = {
    "pdf":  [".pdf"],
    "dxf":  [".dxf"],
    "step": [".step", ".stp"],
    "edr":  [".eprt", ".easm", ".edrw", ".eprtx", ".easmtx", ".edrwt"],  # cover eDrawings variants
    "png":  [".png"],
    "3mf":  [".3mf"],
}

def _norm(s: str) -> str:
    return (s or "").strip()

def _norm_casefold(s: str) -> str:
    return _norm(s).casefold()  # robust case-insensitive normalization

def _stem_for_match(part_number: str, revision: str) -> str:
    # filenames like PARTNUMBER_REV_REVISION.ext
    return f"{_norm(part_number)}_REV_{_norm(revision)}"

def _sha256(path: str, limit_bytes: int) -> str:
    if limit_bytes <= 0:
        return ""
    try:
        sz = os.path.getsize(path)
        if sz > limit_bytes:
            return ""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def discover_part_files(part_number: str, revision: str, roots: Iterable[str], hash_limit_bytes: int = 0) -> List[Dict]:
    """
    Scan configured roots and their typed subfolders for any file whose
    case-insensitive stem equals f"{PN}_REV_{REV}" and extension is in EXT_MAP.
    Returns a list of dicts ready to upsert into PartFile.
    """
    pn_norm  = _norm(part_number)
    rev_norm = _norm(revision)
    if not pn_norm or not rev_norm:
        return []

    wanted_stem = _stem_for_match(pn_norm, rev_norm).casefold()
    found: List[Dict] = []

    for root in roots or []:
        for ext_group, exts in EXT_MAP.items():
            folder = os.path.join(root, ext_group)
            print(folder)
            if not os.path.isdir(folder):
                continue
            try:
                with os.scandir(folder) as it:
                    for entry in it:
                        if not entry.is_file():
                            continue
                        name_cf = entry.name.casefold()
                        # Quick ext filter
                        if not any(name_cf.endswith(e) for e in [x.lower() for x in exts]):
                            continue
                        # Match stem (before last dot)
                        stem_cf = name_cf.rsplit(".", 1)[0]
                        if stem_cf != wanted_stem:
                            continue
                        p = entry.path
                        try:
                            stat = entry.stat()
                            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                            ext = os.path.splitext(entry.name)[1]
                            record = {
                                "part_number": pn_norm,
                                "revision": rev_norm,
                                "ext_group": ext_group,
                                "ext": ext.lower(),
                                "path": p,
                                "size": stat.st_size,
                                "mtime": mtime,
                                "sha256": _sha256(p, hash_limit_bytes) if hash_limit_bytes else "",
                                "source": "scan",
                                "meta_info": {},
                            }
                            found.append(record)
                        except Exception:
                            # skip unreadable entries
                            continue
            except FileNotFoundError:
                continue
    return found

def upsert_part_files(records: List[Dict]) -> int:
    """
    Upsert by unique 'path'. If exists, update metadata; otherwise insert.
    Returns number of inserts.
    """
    inserts = 0
    for r in records:
        doc = PartFile.objects(path=r["path"]).first()
        if doc:
            doc.part_number = r["part_number"]
            doc.revision    = r["revision"]
            doc.ext_group   = r["ext_group"]
            doc.ext         = r["ext"]
            doc.size        = r.get("size")
            doc.mtime       = r.get("mtime")
            if r.get("sha256"):
                doc.sha256 = r["sha256"]
            doc.source      = r.get("source") or doc.source
            meta            = doc.meta_info or {}
            meta.update(r.get("meta_info") or {})
            doc.meta_info   = meta
            doc.save()
        else:
            PartFile(**r).save()
            inserts += 1
    return inserts
