import os, re, hashlib, mimetypes
from datetime import datetime, timezone
from typing import Dict, List
from flask import current_app
from app.models.artifact import PartFile

EXT_MAP: Dict[str, List[str]] = {
    "pdf":  [".pdf"],
    "dxf":  [".dxf"],
    "step": [".step", ".stp"],
    "edr":  [".eprt", ".easm", ".edrw", ".eprtx", ".easmtx", ".edrwt"],
    "png":  [".png"],  # add ".jpg", ".jpeg" here if you need them
    "3mf":  [".3mf"],
}

def _sha256(path: str, limit_bytes: int) -> str:
    if limit_bytes <= 0: return ""
    try:
        if os.path.getsize(path) > limit_bytes: return ""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def _guess_ct(path: str) -> str:
    ct, _ = mimetypes.guess_type(path)
    return ct or "application/octet-stream"

def _patterns(pn: str, rev: str):
    esc_pn, esc_rev = re.escape(pn), re.escape(rev)
    strict = re.compile(rf'^{esc_pn}_REV_{esc_rev}$', re.IGNORECASE)
    loose  = re.compile(rf'^{esc_pn}_REV_{esc_rev}(?:[\s_\-].*)?$', re.IGNORECASE)
    return strict, loose

def _rel_from_root(full_path: str, root: str) -> str | None:
    try:
        rp = os.path.relpath(full_path, root)
        if rp.startswith(".."): return None
        return rp.replace("\\", "/")
    except Exception:
        return None

def discover_part_files_single_root(part_number: str, revision: str) -> List[Dict]:
    pn = (part_number or "").strip()
    rv = (revision or "").strip()
    if not pn or not rv: return []

    root = (current_app.config.get("FILE_ROOT_LOCAL") or "").strip()
    if not root or not os.path.isdir(root): return []

    strict, loose = _patterns(pn, rv)
    found: List[Dict] = []

    for ext_group, exts in EXT_MAP.items():
        folder = os.path.join(root, ext_group)
        if not os.path.isdir(folder): continue

        for dirpath, _, filenames in os.walk(folder):
            for name in filenames:
                name_cf = name.casefold()
                if not any(name_cf.endswith(e) for e in [x.lower() for x in exts]): continue
                stem = os.path.splitext(name)[0]
                if not strict.match(stem) and not loose.match(stem): continue

                full = os.path.join(dirpath, name)
                try: st = os.stat(full)
                except OSError: continue

                rel = _rel_from_root(full, root)
                if rel is None: continue

                rec = {
                    "part_number": pn,
                    "revision": rv,
                    "ext_group": ext_group,
                    "ext": os.path.splitext(name)[1].lower(),
                    "path": full,
                    "rel_path": rel,  # e.g. "png/AWS-B-008968_REV_1.png" or "png/sub/x.png"
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
                    "sha256": _sha256(full, int(current_app.config.get("FILE_HASH_MAX_BYTES", 0) or 0)),
                    "content_type": _guess_ct(full),
                    "source": "scan",
                    "meta_info": {},
                }
                found.append(rec)
    return found

def upsert_part_files(records: List[Dict]) -> int:
    inserts = 0
    for r in records:
        doc = PartFile.objects(path=r["path"]).first()
        if doc:
            for k in ("part_number","revision","ext_group","ext","rel_path","size","mtime","content_type"):
                setattr(doc, k, r.get(k))
            if r.get("sha256"): doc.sha256 = r["sha256"]
            meta = doc.meta_info or {}
            meta.update(r.get("meta_info") or {})
            doc.meta_info = meta
            doc.save()
        else:
            PartFile(**r).save()
            inserts += 1
    return inserts
