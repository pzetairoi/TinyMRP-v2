from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from app.services.timezone_utils import utc_now

_INVALID = re.compile(r'[<>:"/\\\\|?*]+')
_WS = re.compile(r"\s+")


def safe_filename(value: str) -> str:
    """Return a Windows-safe filename stem (no extension)."""
    text = _INVALID.sub("_", (value or ""))
    text = _WS.sub(" ", text).strip()
    text = text.replace(" ", "_")
    text = re.sub(r"_+", "_", text)
    text = text.strip("._-")
    return text or "file"


def timestamp_suffix(now: Optional[datetime] = None, *, include_time: bool = False) -> str:
    now = now or utc_now()
    if include_time:
        return now.strftime("%Y%m%d_%H%M")
    return now.strftime("%Y%m%d")


def build_output_name(
    base: str,
    ext: str,
    *,
    max_len: int = 96,
    include_time: bool = False,
    now: Optional[datetime] = None,
) -> str:
    """Build a safe output filename with timestamp suffix and length cap."""
    ext = (ext or "").strip()
    if ext and not ext.startswith("."):
        ext = "." + ext

    suffix = timestamp_suffix(now=now, include_time=include_time)
    safe = safe_filename(base)
    name = f"{safe}_{suffix}" if safe else suffix

    if max_len and len(name) + len(ext) > max_len:
        trim = max_len - len(ext) - (len(suffix) + 1)
        if trim < 1:
            safe = "file"
            trim = max_len - len(ext) - (len(suffix) + 1)
        safe = safe[:max(1, trim)].rstrip("._-")
        name = f"{safe}_{suffix}"

    return f"{name}{ext}"
