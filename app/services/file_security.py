"""Fail-closed ownership, category, and filesystem controls for part files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable

from flask import current_app, g, has_request_context

from app.models.part import Part
from app.services.app_settings import resolve_file_sources
from app.services.authorization import (
    has_permission,
    part_is_released,
    permission_scope_modes,
    scope_queryset,
)


class FileSecurityError(ValueError):
    """A non-disclosing file ownership or storage validation failure."""


@dataclass(frozen=True)
class StorageRoot:
    source_id: str
    path: Path


_CUSTOMER_FILE_GROUPS = frozenset({"png", "pdf", "datasheet", "3mf", "ply", "stl"})
_SUPPLIER_FILE_GROUPS = frozenset(
    {"png", "pdf", "dxf", "step", "edr", "3mf", "ply", "stl", "datasheet"}
)
_PRODUCTION_FILE_GROUPS = frozenset(
    {"png", "pdf", "dxf", "step", "edr", "3mf", "ply", "stl"}
)


def _resolved_root(value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text or "\x00" in text:
        return None
    try:
        return Path(text).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return None


def managed_storage_roots() -> tuple[StorageRoot, ...]:
    """Return configured managed-file roots without silently broadening them.

    Every managed-file check resolves these roots, so a listing that renders
    hundreds of rows would otherwise re-read app settings and re-resolve the
    same paths once per row. The result is memoised for the current request
    only, so a settings change still takes effect on the next one.
    """
    if has_request_context():
        cached = getattr(g, "_managed_storage_roots", None)
        if cached is not None:
            return cached
    roots = _managed_storage_roots_uncached()
    if has_request_context():
        g._managed_storage_roots = roots
    return roots


def _managed_storage_roots_uncached() -> tuple[StorageRoot, ...]:
    sources: list[dict[str, Any]] = []
    configured = current_app.config.get("FILE_SOURCES")
    try:
        if isinstance(configured, list) and configured:
            sources = [dict(item) for item in configured if isinstance(item, dict)]
        else:
            sources = [
                dict(item)
                for item in resolve_file_sources()
                if isinstance(item, dict)
            ]
    except Exception:
        sources = []

    roots: list[StorageRoot] = []
    seen: set[str] = set()
    for item in sources:
        root = _resolved_root(item.get("local_root"))
        if root is None:
            continue
        key = os.path.normcase(str(root))
        if key in seen:
            continue
        seen.add(key)
        roots.append(StorageRoot(str(item.get("id") or ""), root))

    for key_name in ("FILE_ROOT_LOCAL", "FILES_LOCAL_ROOT"):
        root = _resolved_root(current_app.config.get(key_name))
        if root is None:
            continue
        key = os.path.normcase(str(root))
        if key in seen:
            continue
        seen.add(key)
        roots.append(StorageRoot("", root))
    return tuple(roots)


def associated_storage_root() -> Path:
    from app.services.extra_files import extra_root

    root = _resolved_root(extra_root())
    if root is None:
        raise FileSecurityError("file unavailable")
    return root


def _relative_path(value: Any) -> Path:
    text = str(value or "")
    if not text or "\x00" in text:
        raise FileSecurityError("file unavailable")
    text = text.replace("\\", "/")
    posix = PurePosixPath(text)
    windows = PureWindowsPath(text)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise FileSecurityError("file unavailable")
    return Path(*posix.parts)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except (ValueError, OSError):
        return False


def _dir_file_names(directory: Path) -> set[str] | None:
    """Names of the regular files in `directory`, cached FOR THIS REQUEST ONLY.

    The parts list resolves a thumbnail per file record, and each resolution
    costs several stat calls. On a container bind mount that measured 524 ms of
    a 705 ms response for a single 25-row page. Files belonging to one part
    live in the same directory, so one scandir answers what dozens of stats
    were being asked separately.

    Request-scoped on purpose: a file created or removed between requests must
    be seen. Outside a request context this returns None and callers fall back
    to touching the filesystem directly, so nothing is cached in CLI or worker
    code where the lifetime would be unbounded.

    This is a lookup accelerator ONLY. It never decides whether a path is
    allowed - containment is still proved by _validate_candidate against the
    resolved root.
    """
    if not has_request_context():
        return None
    cache = getattr(g, "_tinymrp_dir_listing_cache", None)
    if cache is None:
        cache = {}
        g._tinymrp_dir_listing_cache = cache
    key = os.path.normcase(str(directory))
    if key in cache:
        return cache[key]
    try:
        names = {entry.name for entry in os.scandir(directory) if entry.is_file()}
    except OSError:
        names = set()
    cache[key] = names
    return names


def _candidate_file_exists(candidate: Path) -> bool:
    """Does this exact path exist as a regular file? Cached per request."""
    names = _dir_file_names(candidate.parent)
    if names is None:
        return candidate.is_file()
    return candidate.name in names


def _validate_candidate(
    candidate: Path,
    root: Path,
    *,
    must_exist: bool,
) -> Path:
    try:
        resolved_root = root.resolve(strict=False)
        resolved = candidate.resolve(strict=must_exist)
    except (OSError, RuntimeError, ValueError) as exc:
        raise FileSecurityError("file unavailable") from exc
    if not _inside(resolved, resolved_root):
        raise FileSecurityError("file unavailable")
    if resolved.exists() and not resolved.is_file():
        raise FileSecurityError("file unavailable")
    if must_exist and not resolved.is_file():
        raise FileSecurityError("file unavailable")
    return resolved


def _ordered_roots(record: Any, roots: Iterable[StorageRoot]) -> list[StorageRoot]:
    values = list(roots)
    source_id = str(getattr(record, "source", "") or "").strip().casefold()
    if not source_id:
        return values
    matching = [
        root for root in values if root.source_id.strip().casefold() == source_id
    ]
    return matching or values


def resolve_managed_path(
    file_record: Any,
    *,
    kind: str = "file",
    must_exist: bool = True,
) -> Path:
    """Resolve a managed path from trusted metadata inside an approved root."""

    roots = managed_storage_roots()
    if not roots:
        raise FileSecurityError("file unavailable")

    if kind == "thumb":
        rel = _relative_path(getattr(file_record, "thumb_rel_path", ""))
        thumb_roots: list[StorageRoot] = []
        seen_thumb_roots: set[str] = set()
        for key_name in ("FILE_ROOT_LOCAL", "FILES_LOCAL_ROOT"):
            root = _resolved_root(current_app.config.get(key_name))
            if root is None:
                continue
            key = os.path.normcase(str(root))
            if key in seen_thumb_roots:
                continue
            seen_thumb_roots.add(key)
            thumb_roots.append(StorageRoot("", root))
        selected_roots = thumb_roots or list(roots)
        candidates = [
            _validate_candidate(root.path / rel, root.path, must_exist=must_exist)
            for root in selected_roots
            if _candidate_file_exists(root.path / rel) or not must_exist
        ]
    else:
        stored_path = str(getattr(file_record, "path", "") or "").strip()
        native_path = Path(stored_path) if stored_path else None
        foreign_absolute = bool(
            stored_path
            and (
                PurePosixPath(stored_path.replace("\\", "/")).is_absolute()
                or PureWindowsPath(stored_path).is_absolute()
                or PureWindowsPath(stored_path).drive
            )
        )
        if native_path is not None and native_path.is_absolute():
            containing = [
                root
                for root in roots
                if _inside(native_path.resolve(strict=False), root.path)
            ]
            if len(containing) != 1:
                raise FileSecurityError("file unavailable")
            return _validate_candidate(
                native_path,
                containing[0].path,
                must_exist=must_exist,
            )
        if foreign_absolute:
            raise FileSecurityError("file unavailable")
        rel_value = getattr(file_record, "rel_path", "") or stored_path
        rel = _relative_path(rel_value)
        candidates = [
            _validate_candidate(root.path / rel, root.path, must_exist=must_exist)
            for root in _ordered_roots(file_record, roots)
            if (root.path / rel).exists() or not must_exist
        ]

    unique = {os.path.normcase(str(path)): path for path in candidates}
    if len(unique) != 1:
        raise FileSecurityError("file unavailable")
    return next(iter(unique.values()))


def resolve_associated_path(
    file_record: Any,
    *,
    must_exist: bool = True,
) -> Path:
    root = associated_storage_root()
    rel = _relative_path(getattr(file_record, "rel_path", ""))
    return _validate_candidate(root / rel, root, must_exist=must_exist)


def exact_file_part(
    user: Any,
    part_number: Any,
    revision: Any,
    *,
    permission: str = "files.read",
    mutable: bool = False,
) -> Part | None:
    """Return the exact owning part only when file and part scope both allow it."""

    pn = str(part_number or "").strip()
    rev = str(revision or "").strip()
    if not pn or not has_permission(user, permission):
        return None
    try:
        part = (
            scope_queryset(Part.objects, user, "parts")
            .filter(part_number__iexact=pn, revision__iexact=rev)
            .first()
        )
    except Exception:
        return None
    if part is None or (mutable and part_is_released(part)):
        return None
    return part


def managed_file_category_allowed(user: Any, file_record: Any) -> bool:
    return managed_file_group_allowed(
        user,
        getattr(file_record, "ext_group", ""),
    )


def managed_file_group_allowed(user: Any, ext_group: Any) -> bool:
    modes = permission_scope_modes(user, "files.read", resource_type="parts")
    if "global" in modes:
        return True
    group = str(ext_group or "").strip().lower()
    allowed: set[str] = set()
    if "customer" in modes:
        allowed.update(_CUSTOMER_FILE_GROUPS)
    if "supplier" in modes:
        allowed.update(_SUPPLIER_FILE_GROUPS)
    if "assigned" in modes:
        allowed.update(_PRODUCTION_FILE_GROUPS)
    return group in allowed


def associated_file_category_allowed(user: Any, _file_record: Any) -> bool:
    """Associated-file categories are unclassified, so portal reads stay closed."""

    modes = permission_scope_modes(user, "files.read", resource_type="parts")
    return "global" in modes


def managed_file_read_allowed(user: Any, file_record: Any) -> bool:
    return bool(
        exact_file_part(
            user,
            getattr(file_record, "part_number", ""),
            getattr(file_record, "revision", ""),
        )
        and managed_file_category_allowed(user, file_record)
    )


def managed_file_metadata_allowed(user: Any, file_record: Any) -> bool:
    if not managed_file_read_allowed(user, file_record):
        return False
    try:
        resolve_managed_path(file_record, must_exist=False)
        return True
    except FileSecurityError:
        return False


def managed_file_path_allowed(file_record: Any) -> bool:
    try:
        resolve_managed_path(file_record, must_exist=False)
        return True
    except FileSecurityError:
        return False


def managed_thumbnail_available(file_record: Any) -> bool:
    try:
        return resolve_managed_path(
            file_record,
            kind="thumb",
            must_exist=True,
        ).is_file()
    except FileSecurityError:
        return False


def associated_file_read_allowed(user: Any, file_record: Any) -> bool:
    return bool(
        exact_file_part(
            user,
            getattr(file_record, "part_number", ""),
            getattr(file_record, "revision", ""),
        )
        and associated_file_category_allowed(user, file_record)
    )


def associated_file_path_allowed(file_record: Any) -> bool:
    try:
        resolve_associated_path(file_record, must_exist=False)
        return True
    except FileSecurityError:
        return False
