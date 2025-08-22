from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Iterable, Tuple
from PIL import Image
from flask import current_app
from app.models.artifact import PartFile

def _subdir() -> str:
    return (current_app.config.get("THUMB_SUBDIR") or "thumbs").strip("/")

def _max_size() -> Tuple[int, int]:
    w = int(current_app.config.get("THUMB_MAX_W") or 320)
    h = int(current_app.config.get("THUMB_MAX_H") or 240)
    return (w, h)

def _fmt() -> str:
    f = (current_app.config.get("THUMB_FORMAT") or "PNG").upper()
    return "PNG" if f not in ("PNG","JPEG","JPG","WEBP") else f

def _root_local() -> str:
    return (current_app.config.get("FILE_ROOT_LOCAL") or "").rstrip("/\\")
    
def _ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def _thumb_rel_for(src_rel: str) -> str:
    # mirror under thumbs/, preserving subfolders after the top-level ext_group
    # e.g., "png/A-B_REV_1.png" -> "thumbs/png/A-B_REV_1.png"
    return "/".join([_subdir(), src_rel.replace("\\", "/")])

def _abs(path_rel: str) -> str:
    return os.path.join(_root_local(), path_rel.replace("/", os.sep))

def _needs_rebuild(src_abs: str, dst_abs: str) -> bool:
    if not os.path.isfile(src_abs):
        return False
    if not os.path.isfile(dst_abs):
        return True
    try:
        sm = os.path.getmtime(src_abs)
        dm = os.path.getmtime(dst_abs)
        return sm > dm
    except Exception:
        return True

def _gen_one(src_abs: str, dst_abs: str):
    fmt = _fmt()
    maxw, maxh = _max_size()
    _ensure_dir(os.path.dirname(dst_abs))
    with Image.open(src_abs) as im:
        im = im.convert("RGBA") if fmt == "PNG" else im.convert("RGB")
        im.thumbnail((maxw, maxh))   # preserves aspect ratio
        save_kwargs = {}
        if fmt in ("JPEG", "JPG"):
            save_kwargs["quality"] = int(current_app.config.get("THUMB_QUALITY") or 88)
            save_kwargs["optimize"] = True
        if fmt == "PNG":
            save_kwargs["optimize"] = True
        im.save(dst_abs, fmt, **save_kwargs)

def generate_thumbs_for_artifacts(docs: Iterable[PartFile]) -> int:
    """
    For each PNG artifact, generate/update its thumbnail under FILE_ROOT_LOCAL/thumbs/...
    Returns number of thumbnails created/updated.
    """
    root = _root_local()
    if not root or not os.path.isdir(root):
        return 0

    count = 0
    for d in docs:
        if (d.ext_group or "").lower() != "png":
            continue
        if not d.rel_path or not d.path:
            continue
        src_abs = d.path
        rel = d.rel_path
        thumb_rel = _thumb_rel_for(rel)  # thumbs/png/...
        thumb_abs = _abs(thumb_rel)
        if _needs_rebuild(src_abs, thumb_abs):
            try:
                _gen_one(src_abs, thumb_abs)
            except Exception as ex:
                # optionally log ex
                continue
            # set bookkeeping
            d.thumb_rel_path = thumb_rel
            d.thumb_mtime = datetime.fromtimestamp(os.path.getmtime(thumb_abs), tz=timezone.utc)
            d.save()
            count += 1
        else:
            # ensure DB points to existing thumb if missing
            if not d.thumb_rel_path:
                d.thumb_rel_path = thumb_rel
                try:
                    d.thumb_mtime = datetime.fromtimestamp(os.path.getmtime(thumb_abs), tz=timezone.utc)
                except Exception:
                    pass
                d.save()
    return count

def generate_thumbs_for_parts(part_numbers: Iterable[Tuple[str, str]] | Iterable[str]) -> int:
    """
    Accepts iterable of (pn, rev) or pn. Generates thumbnails for all PNG docs that match.
    """
    root = _root_local()
    if not root or not os.path.isdir(root):
        return 0

    # normalize input
    pairs = []
    for item in part_numbers:
        if isinstance(item, tuple):
            pairs.append(item)
        else:
            pairs.append((str(item), None))
    total = 0
    for pn, rev in pairs:
        q = {"part_number": pn, "ext_group": "png"}
        if rev is not None:
            q["revision"] = rev
        docs = PartFile.objects(**q)
        total += generate_thumbs_for_artifacts(docs)
    return total
