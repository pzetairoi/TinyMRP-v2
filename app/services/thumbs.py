from typing import Iterable, List, Optional
from flask import current_app
from app.models.artifact import PartFile
from app.services.file_security import (
    managed_file_category_allowed,
    managed_file_metadata_allowed,
    managed_file_path_allowed,
    managed_thumbnail_available,
)
from app.services.files_access import file_url_for
from app.services.part_norm import clean_rev

def _urls_for(pn: str, rev: Optional[str], *, is_dwg: bool, user=None):
    """Return best-first URLs for preview/drawing PNGs.

    Order: preview prefers thumbnails; drawings prefer originals.
    """
    rev_clean = rev or ""
    rows = PartFile.objects(
        part_number__iexact=pn,
        revision__iexact=rev_clean,
        ext_group="png",
        is_dwg=is_dwg,
    )
    if not rows:
        return []
    pf = rows.first()
    if user is not None and not managed_file_metadata_allowed(user, pf):
        return []

    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")
    prefer_thumb = not is_dwg
    out = _urls_for_doc(pf, http_base, prefer_thumb=prefer_thumb)
    return _dedup_urls(out)

def preview_png_urls_for(pn: str, rev: str | None, *, user=None):
    return _urls_for(pn, rev, is_dwg=False, user=user)

def drawing_png_urls_for(pn: str, rev: str | None, *, user=None):
    return _urls_for(pn, rev, is_dwg=True, user=user)

# kept for backward compat – use only for places that truly want preview images
def thumb_urls_for(pn: str, rev: str | None, *, user=None):
    return preview_png_urls_for(pn, rev, user=user)


def preview_png_urls_map(
    pairs: Iterable[tuple[str, str | None]],
    *,
    user=None,
) -> dict[tuple[str, str], List[str]]:
    requested: dict[tuple[str, str], tuple[str, str]] = {}
    for pn, rev in pairs:
        pn_clean = str(pn or "").strip()
        rev_clean = clean_rev(rev or "")
        if not pn_clean:
            continue
        requested[(pn_clean.lower(), rev_clean.lower())] = (pn_clean, rev_clean)
    if not requested:
        return {}

    authorised = None
    if user is not None:
        from app.services.authorization import authorised_part_pairs

        authorised = authorised_part_pairs(user, requested.values())
    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")
    out: dict[tuple[str, str], List[str]] = {}
    pn_list = sorted({pn for pn, _rev in requested.values()})
    rows = (
        PartFile.objects(part_number__in=pn_list, ext_group="png", is_dwg=False)
        .only(
            "part_number",
            "revision",
            "ext_group",
            "is_dwg",
            "path",
            "rel_path",
            "source",
            "http_url",
            "thumb_rel_path",
            "mtime",
            "mtime_iso",
        )
        .order_by("-mtime_iso", "-mtime", "rel_path")
    )
    for row in rows:
        match = requested.get((str(getattr(row, "part_number", "") or "").strip().lower(), clean_rev(getattr(row, "revision", "") or "").lower()))
        if not match or match in out:
            continue
        if user is not None:
            key = (match[0].casefold(), match[1].casefold())
            if (
                key not in (authorised or frozenset())
                or not managed_file_category_allowed(user, row)
                or not managed_file_path_allowed(row)
            ):
                continue
        out[match] = _dedup_urls(_urls_for_doc(row, http_base, prefer_thumb=True))
    return out


def thumb_urls_map(
    pairs: Iterable[tuple[str, str | None]],
    *,
    user=None,
) -> dict[tuple[str, str], List[str]]:
    return preview_png_urls_map(pairs, user=user)


# helper: build URL list for a single PartFile doc
def _urls_for_doc(d: PartFile, http_base: str, *, prefer_thumb: bool = True) -> List[str]:
    urls: List[str] = []
    try:
        if prefer_thumb and managed_thumbnail_available(d):
            urls.append(file_url_for(d, kind="thumb"))
        urls.append(file_url_for(d, kind="file"))
    except Exception:
        pass
    return urls

def _dedup_urls(urls: List[str]) -> List[str]:
    seen = set()
    dedup: List[str] = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            dedup.append(u)
    return dedup

def drawing_urls_for(pn: str, rev_pref: Optional[str]) -> List[str]:
    """
    Prefer PNG artifacts whose rel_path contains '_DWG' (case-insensitive).
    If none exist, fall back to thumb_urls_for(pn, rev_pref).
    Returns best-first URL list: HTTP thumbnail -> HTTP original -> token fallback.
    """
    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")
    q = (PartFile.objects(part_number__iexact=pn, ext_group="png")
         .only("path", "rel_path", "thumb_rel_path", "revision", "mtime")
         .order_by("-mtime", "path"))
    docs = list(q)
    if not docs:
        return thumb_urls_for(pn, rev_pref)

    def is_dwg(d: PartFile) -> bool:
        return "_DWG" in ((d.rel_path or d.path or "").upper())

    # If revision provided, stay within that revision only.
    if rev_pref is not None:
        pref = rev_pref or ""
        docs = [d for d in docs if (d.revision or "") == pref]
        if not docs:
            return thumb_urls_for(pn, pref)

    dwg_docs = [d for d in docs if is_dwg(d)]
    if dwg_docs:
        return _dedup_urls(_urls_for_doc(dwg_docs[0], http_base, prefer_thumb=False))

    # fallback to standard thumbnail policy
    return thumb_urls_for(pn, rev_pref)
