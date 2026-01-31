from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Iterable, Tuple
import io
from PIL import Image, ImageOps, ImageFilter
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

def _gen_one(src_abs: str, dst_abs: str, *, remove_bg: bool = True):
    fmt = _fmt()
    maxw, maxh = _max_size()
    _ensure_dir(os.path.dirname(dst_abs))

    def _crop_and_background_pil(im: Image.Image) -> Image.Image:
        """
        Approximate OLD/tinylib/imageprocess.cropandbackground using Pillow:
        - Build a mask of non-white pixels (any value > 0 after inverted grayscale)
        - Morphologically close then open with 3x3 to smooth small holes
        - Set alpha to this mask (transparent background)
        - Crop to bounding box if sufficiently large
        """
        # Work on RGB base
        base_rgb = im.convert("RGB")
        # Invert grayscale so non-white becomes >0
        inv = ImageOps.invert(base_rgb.convert("L"))
        # Threshold at >0
        mask = inv.point(lambda p: 255 if p > 0 else 0, mode='1').convert('L')
        # Close (dilate then erode) and Open (erode then dilate) with 3x3
        mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
        mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))

        # Compose RGBA with computed alpha
        rgba = base_rgb.convert("RGBA")
        rgba.putalpha(mask)

        # Crop if area is big enough (match old heuristic ~8000 px)
        bbox = mask.getbbox()
        if bbox:
            x0, y0, x1, y1 = bbox
            w, h = (x1 - x0), (y1 - y0)
            if w * h > 8000:
                rgba = rgba.crop(bbox)
        return rgba

    with Image.open(src_abs) as im:
        # Apply crop + transparent background first, then scale (unless disabled)
        processed = _crop_and_background_pil(im) if remove_bg else im.convert("RGBA")
        processed.thumbnail((maxw, maxh))   # preserves aspect ratio

        # Aggressive size control without touching config
        # Tweak these to taste:
        target_kb = 10  # target maximum thumbnail size in kilobytes

        # JPEG/WEBP: binary search quality to reach target
        if fmt in ("JPEG", "JPG"):
            # Flatten onto white for formats without alpha
            bg = Image.new("RGB", processed.size, (255, 255, 255))
            bg.paste(processed, mask=processed.split()[-1])

            lo, hi = 35, 92
            best = None
            for _ in range(7):
                q = (lo + hi) // 2
                buf = io.BytesIO()
                bg.save(buf, "JPEG", quality=q, optimize=True, progressive=True, subsampling=2)
                size_kb = len(buf.getvalue()) / 1024.0
                if size_kb > target_kb:
                    hi = q - 1
                else:
                    best = buf.getvalue(); lo = q + 1
            if best is None:
                buf = io.BytesIO(); bg.save(buf, "JPEG", quality=max(25, hi), optimize=True, progressive=True, subsampling=2)
                best = buf.getvalue()
            with open(dst_abs, "wb") as f:
                f.write(best)
            return

        if fmt == "WEBP":
            lo, hi = 35, 92
            best = None
            for _ in range(7):
                q = (lo + hi) // 2
                buf = io.BytesIO()
                processed.save(buf, "WEBP", quality=q, method=6)
                size_kb = len(buf.getvalue()) / 1024.0
                if size_kb > target_kb:
                    hi = q - 1
                else:
                    best = buf.getvalue(); lo = q + 1
            if best is None:
                buf = io.BytesIO(); processed.save(buf, "WEBP", quality=max(25, hi), method=6)
                best = buf.getvalue()
            with open(dst_abs, "wb") as f:
                f.write(best)
            return

        # PNG path: preserve full alpha and shrink by color quantization + optional downscale
        # (No magenta background -> no pink halo.)
        scale_steps = [1.0, 0.9, 0.8, 0.7, 0.6]
        palette_trials = [128, 96, 64, 48, 32]

        best_bytes = None
        best_size = 1e9
        for s in scale_steps:
            if s != 1.0:
                w, h = processed.size
                new_wh = (max(1, int(w * s)), max(1, int(h * s)))
                work = processed.resize(new_wh, Image.LANCZOS)
            else:
                work = processed

            alpha = work.split()[-1] if work.mode == "RGBA" else None
            rgb = work.convert("RGB")

            for colors in palette_trials:
                pal_rgb = rgb.quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.FLOYDSTEINBERG).convert("RGB")
                out_rgba = pal_rgb.convert("RGBA")
                if alpha is not None:
                    out_rgba.putalpha(alpha)

                buf = io.BytesIO()
                out_rgba.save(buf, "PNG", optimize=True, compress_level=9)
                b = buf.getvalue()
                size_kb = len(b) / 1024.0
                # Track best regardless
                if size_kb < best_size:
                    best_size = size_kb
                    best_bytes = b
                if size_kb <= target_kb:
                    with open(dst_abs, "wb") as f:
                        f.write(b)
                    return

        # Fallback: write best attempt
        if best_bytes is None:
            buf = io.BytesIO(); processed.save(buf, "PNG", optimize=True, compress_level=9)
            best_bytes = buf.getvalue()
        with open(dst_abs, "wb") as f:
            f.write(best_bytes)

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
        # Compute absolute source path from rel_path (preferred). Fallback to path.
        if not d.rel_path and not d.path:
            continue
        rel = d.rel_path or d.path
        # If stored path is absolute, keep it; otherwise resolve against FILE_ROOT_LOCAL
        src_abs = d.path if (d.path and os.path.isabs(d.path)) else _abs(rel)
        thumb_rel = _thumb_rel_for(rel)  # thumbs/png/...
        thumb_abs = _abs(thumb_rel)
        if _needs_rebuild(src_abs, thumb_abs):
            try:
                _gen_one(src_abs, thumb_abs, remove_bg=not bool(getattr(d, "is_dwg", False)))
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
        q = {"part_number__iexact": pn, "ext_group": "png"}
        if rev is not None:
            q["revision__iexact"] = rev
        docs = PartFile.objects(**q)
        total += generate_thumbs_for_artifacts(docs)
    return total
