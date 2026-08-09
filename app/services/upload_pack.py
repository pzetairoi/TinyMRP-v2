from __future__ import annotations
import logging
import hashlib
import io
import mimetypes
import os
import re
import shutil
import stat
import tempfile
import time
import unicodedata
import uuid
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable
from flask import current_app, has_app_context
from mongoengine.queryset.visitor import Q
from pymongo import DeleteMany, InsertOne, UpdateOne
from app.models.artifact import PartFile
from app.models.bom import BOMLink
from app.models.extra_file import PartExtraFile
from app.models.import_journal import ImportJournal
from app.models.part import Part
from app.services.attrs import normalize_record_attrs
from app.services.canonical_fields import (
    APPROVED_BY_FIELD_ID,
    APPROVED_DATE_FIELD_ID,
    APPROVED_FIELD_ID,
    canonical_alias_index,
    canonical_attr_key,
    resolve_approval,
    set_runtime_canonical_aliases,
)
from app.services.extra_files import extra_rel_path, rev_from_token, validated_upload_filename
from app.services.field_config import field_index, get_field_config
from app.services.filescan import discover_part_files, upsert_part_files_detailed
from app.services.import_zip import (
    _aggregate_links,
    _base_pn,
    _normalize_part,
    _parse_flatbom,
    _parse_treebom,
)
from app.services.part_materialized import sync_part_materialized_fields
from app.services.part_norm import clean_pn, clean_rev
from app.services.thumbs_gen import generate_thumbs_for_parts
from app.services.timezone_utils import utc_iso, utc_now

logger = logging.getLogger(__name__)
DATA_MODES = {"skip", "fill_blanks", "replace_unapproved", "replace_all"}
BOM_MODES = {"skip", "fill_if_empty", "replace_unapproved", "replace_all"}
FILE_MODES = {"skip", "add_missing", "replace_unapproved", "replace_all"}
APPROVAL_MODES = {"preserve", "import_unapproved", "replace_all"}
IMPORT_PERMISSIONS = {
    "imports.preview",
    "imports.execute_low_risk",
    "imports.execute_approved",
    "imports.override_approved",
}
_APPROVAL_FIELDS = {APPROVED_FIELD_ID, APPROVED_BY_FIELD_ID, APPROVED_DATE_FIELD_ID}
_IDENTITY_KEYS = {"partnumber", "part_number", "pn", "revision", "rev"}
_TOP_LEVEL_FIELDS = {
    "description": "description",
    "category": "category",
    "uom": "uom",
    "manufacturer": "manufacturer",
    "mfr_part": "mfr_part",
}
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

_ALLOWED_COMPRESSION_METHODS = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
_DELIVERABLE_EXTENSIONS = {
    "png": {"png"},
    "pdf": {"pdf"},
    "dxf": {"dxf"},
    "step": {"step", "stp"},
    "edr": {"edr", "eprt", "easm", "edrw"},
    "3mf": {"3mf"},
    "ply": {"ply"},
    "stl": {"stl"},
    "datasheet": {"pdf", "jpg", "jpeg", "png"},
}


class ArchiveLimitError(ValueError):
    """The archive exceeds a configured resource budget."""


class ArchiveTimeoutError(ArchiveLimitError):
    """Archive validation exceeded its configured wall-clock budget."""


def _positive_limit(config: object, name: str, fallback: int) -> int:
    try:
        value = int(getattr(config, "get", lambda *_: fallback)(name, fallback))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


def _archive_limits(config: object) -> dict[str, int]:
    mebibyte = 1024 * 1024
    return {
        "compressed": _positive_limit(config, "UPLOAD_PACK_MAX_ZIP_MB", 200)
        * mebibyte,
        "entry": _positive_limit(config, "UPLOAD_PACK_MAX_FILE_MB", 256)
        * mebibyte,
        "total": _positive_limit(config, "UPLOAD_PACK_MAX_TOTAL_MB", 1024)
        * mebibyte,
        "entries": _positive_limit(config, "UPLOAD_PACK_MAX_FILES", 5000),
        "ratio": _positive_limit(config, "UPLOAD_PACK_MAX_COMPRESSION_RATIO", 100),
        "path": _positive_limit(config, "UPLOAD_PACK_MAX_PATH_CHARS", 240),
        "seconds": _positive_limit(config, "UPLOAD_PACK_MAX_SECONDS", 120),
    }


def _check_archive_deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise ArchiveTimeoutError("ZIP validation exceeded configured time limit")


class ImportPermissionError(ValueError):
    def __init__(self, missing: Iterable[str]):
        self.missing_permissions = sorted(set(missing))
        super().__init__(
            "missing import permission(s): " + ", ".join(self.missing_permissions)
        )
class ImportScopeError(ValueError):
    def __init__(self, pairs: Iterable[tuple[str, str]]):
        self.denied_pairs = sorted(set(pairs))
        super().__init__(
            "part/revision outside the caller's mutable scope: "
            + ", ".join(f"{pn}:{rev or '(blank)'}" for pn, rev in self.denied_pairs)
        )
def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True
def _json_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return utc_iso(value) or value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
def _safe_zip_name(name: str) -> str | None:
    if (
        not name
        or "\x00" in name
        or any(ord(character) < 32 for character in name)
    ):
        return None
    normalized = unicodedata.normalize("NFC", name.replace("\\", "/"))
    if normalized.startswith("/") or _DRIVE_RE.match(normalized):
        return None
    segments = normalized.split("/")
    if not segments or any(segment in {"", ".", ".."} for segment in segments):
        return None
    return "/".join(segments)
def _safe_destination(root: str, relative: str) -> str:
    destination = os.path.abspath(os.path.join(root, relative.replace("/", os.sep)))
    if os.path.commonpath([os.path.normcase(destination), os.path.normcase(os.path.abspath(root))]) != os.path.normcase(os.path.abspath(root)):
        raise ValueError(f"unsafe output path: {relative}")
    return destination
def _deliverable_identity(filename: str) -> tuple[str, str, bool] | None:
    base, _extension = os.path.splitext(os.path.basename(filename or ""))
    drawing = base.casefold().endswith("_dwg")
    if drawing:
        base = base[:-4]
    marker = base.upper().rfind("_REV_")
    if marker <= 0:
        return None
    pn = clean_pn(base[:marker])
    return (pn, clean_rev(base[marker + 5 :]), drawing) if pn else None
def _root_preview_data_uri(
    files: list[dict[str, Any]],
    root: tuple[str, str] | None,
) -> str:
    """Return the root part's preview PNG as an inline data URI.

    Used to show what is being imported before anything is written. It is held
    in the response only -- nothing is stored, so it cannot collide with or
    outlive the thumbnails that an applied import generates.
    """

    if not root:
        return ""
    source = next(
        (
            item
            for item in files
            if item["kind"] == "managed"
            and item["pair"] == root
            and item["identity"][0] == "png"
            and not item["identity"][2]
        ),
        None,
    )
    if source is None:
        return ""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(source["bytes"])) as image:
            image = image.convert("RGBA")
            image.thumbnail((160, 160))
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
    except Exception:
        return ""
    encoded = __import__("base64").b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _claim_pair(
    parts: dict[tuple[str, str], dict[str, Any]],
    pair: tuple[str, str],
    entry: str,
    diagnostics: dict[str, Any],
) -> bool:
    """Return whether a packed file belongs to a part the BOM declares.

    Only FLATBOM/TREEBOM rows create parts. A file whose name does not resolve
    to one of those pairs is reported and skipped rather than inventing a
    part/revision -- CAD exports routinely include temp artefacts whose names
    otherwise parse into a bogus revision.
    """

    if pair in parts:
        return True
    diagnostics["warnings"].append(
        {
            "severity": "warning",
            "stage": "files.orphan",
            "message": (
                f"Skipped {entry}: no BOM entry for {pair[0]}"
                f"{' rev ' + pair[1] if pair[1] else ''}."
            ),
        }
    )
    return False


def _shell(pair: tuple[str, str]) -> dict[str, Any]:
    return {
        "part_number": pair[0],
        "revision": pair[1],
        "description": "",
        "category": "",
        "uom": "EA",
        "attrs": {},
    }
def _load_manifest(zf: zipfile.ZipFile) -> dict[tuple[str, str, str], dict[str, str]]:
    name = next(
        (
            item
            for item in zf.namelist()
            if _safe_zip_name(item) in {"extra/_manifest.json", "extra/manifest.json"}
        ),
        None,
    )
    if not name:
        return {}
    try:
        payload = __import__("json").loads(zf.read(name).decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return {}
    output = {}
    for item in payload.get("files", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        key = (
            clean_pn(item.get("pn")),
            clean_rev(item.get("rev")),
            os.path.basename(str(item.get("name") or "")).casefold(),
        )
        if key[0] and key[2]:
            output[key] = {str(k): str(v or "") for k, v in item.items()}
    return output
def _policy_options(
    *,
    data_mode: object = None,
    bom_mode: object = None,
    file_mode: object = None,
    approval_mode: object = None,
) -> dict[str, Any]:
    """Validate the four independent import policies, defaulting to fill-only."""
    values = {
        "data_mode": str(data_mode or "fill_blanks").strip().lower(),
        "bom_mode": str(bom_mode or "fill_if_empty").strip().lower(),
        "file_mode": str(file_mode or "add_missing").strip().lower(),
        "approval_mode": str(approval_mode or "preserve").strip().lower(),
    }
    valid = {
        "data_mode": DATA_MODES,
        "bom_mode": BOM_MODES,
        "file_mode": FILE_MODES,
        "approval_mode": APPROVAL_MODES,
    }
    for name, allowed in valid.items():
        if values[name] not in allowed:
            raise ValueError(f"invalid {name}: {values[name]}")
    return values


def _validated_zip_members(
    zf: zipfile.ZipFile,
    limits: dict[str, int],
    deadline: float,
) -> dict[str, zipfile.ZipInfo]:
    infos = zf.infolist()
    if len(infos) > limits["entries"]:
        raise ArchiveLimitError("ZIP exceeds configured entry count limit")

    members: dict[str, zipfile.ZipInfo] = {}
    seen: set[str] = set()
    total_size = 0
    for info in infos:
        _check_archive_deadline(deadline)
        raw_name = info.filename[:-1] if info.is_dir() else info.filename
        safe = _safe_zip_name(raw_name)
        if not safe:
            raise ValueError("unsafe or ambiguous ZIP entry path")
        if len(safe) > limits["path"]:
            raise ArchiveLimitError("ZIP entry path exceeds configured length limit")
        collision_key = safe.casefold()
        if collision_key in seen:
            raise ValueError("ZIP contains duplicate or ambiguous entry paths")
        seen.add(collision_key)
        if info.flag_bits & 0x1:
            raise ValueError("encrypted ZIP entries are not supported")
        unix_mode = (info.external_attr >> 16) & 0xFFFF
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise ValueError("ZIP links are not supported")
        if info.is_dir():
            continue
        if info.compress_type not in _ALLOWED_COMPRESSION_METHODS:
            raise ValueError("unsupported ZIP compression method")
        if info.file_size > limits["entry"]:
            raise ArchiveLimitError("ZIP entry exceeds configured size limit")
        total_size += info.file_size
        if total_size > limits["total"]:
            raise ArchiveLimitError("ZIP exceeds configured uncompressed size limit")
        if info.file_size and info.file_size > limits["ratio"] * max(
            info.compress_size, 1
        ):
            raise ArchiveLimitError("ZIP entry exceeds configured compression ratio")
        members[safe] = info
    return members


def _validate_deliverable_extension(group: str, filename: str) -> str:
    extension = os.path.splitext(filename)[1].lstrip(".").casefold()
    if extension not in _DELIVERABLE_EXTENSIONS.get(group, set()):
        raise ValueError(f"unsupported file type for {group} deliverables")
    return extension


def parse_import_package(
    file_bytes: bytes,
    filename: str,
    options: dict[str, Any],
) -> dict[str, Any]:
    """Validate and parse every ZIP member exactly once."""
    started = time.perf_counter()
    config = current_app.config if has_app_context() else {}
    limits = _archive_limits(config)
    deadline = time.monotonic() + limits["seconds"]
    if Path(filename).suffix.casefold() != ".zip":
        raise ValueError("upload package must be a .zip file")
    if len(file_bytes) > limits["compressed"]:
        raise ArchiveLimitError("ZIP exceeds configured compressed size limit")
    diagnostics: dict[str, Any] = {
        "warnings": [],
        "errors": [],
        "bom_integrity_status": "ok",
        "flat_lines_failed_parse": 0,
        "flat_lines_skipped_not_dict": 0,
        "rows_skipped_blank_part": 0,
        "tree_rows_failed_qty": 0,
        "bom_repeated_subassemblies": 0,
        "bom_repeated_subassembly_copies_collapsed": 0,
        "bom_definition_conflicts": 0,
        "tree_links_skipped_integrity": 0,
        "zip_open_count": 1,
        "flatbom_parse_count": 0,
        "treebom_parse_count": 0,
    }
    parts: dict[tuple[str, str], dict[str, Any]] = {}
    # Rows whose identity collides with one already accepted; the operator picks
    # the winner rather than the import failing or silently keeping the last row.
    duplicates: dict[tuple[str, str], list[dict[str, Any]]] = {}
    links: list[tuple[str, str, str, str, float, list[dict[str, Any]]]] = []
    files: list[dict[str, Any]] = []
    root: tuple[str, str] | None = None
    try:
        archive = zipfile.ZipFile(io.BytesIO(file_bytes))
    except zipfile.BadZipFile as exc:
        raise ValueError("invalid ZIP package") from exc
    with archive as zf:
        safe_infos = _validated_zip_members(zf, limits, deadline)
        flat_names = [
            name for name in safe_infos if name.casefold().endswith("_flatbom.txt")
        ]
        tree_names = [
            name for name in safe_infos if name.casefold().endswith("_treebom.txt")
        ]
        if len(flat_names) > 1 or len(tree_names) > 1:
            raise ValueError("package must contain at most one FLATBOM and one TREEBOM")
        if flat_names:
            diagnostics["flatbom_parse_count"] = 1
            text = zf.read(safe_infos[flat_names[0]]).decode("utf-8-sig", errors="replace")
            for line_number, row in _parse_flatbom(
                text,
                flat_names[0],
                report=diagnostics,
            ):
                normalized = _normalize_part(row)
                key = (normalized["part_number"], normalized["revision"])
                if not key[0]:
                    diagnostics["warnings"].append(
                        {
                            "severity": "warning",
                            "stage": "flatbom.identity",
                            "line_number": line_number,
                            "message": "FLATBOM row has no part number.",
                        }
                    )
                    continue
                if key in parts:
                    # SolidWorks exports virtual components as "PN^parent", and
                    # several of them collapse onto one part number. Report the
                    # clash instead of silently overwriting so the operator can
                    # choose which row wins.
                    duplicates.setdefault(key, [parts[key]]).append(normalized)
                    continue
                parts[key] = normalized
        if tree_names:
            diagnostics["treebom_parse_count"] = 1
            text = zf.read(safe_infos[tree_names[0]]).decode("utf-8-sig", errors="replace")
            raw_rows = [
                columns
                for line in text.splitlines()
                if len(columns := line.split("\t")) >= 4
                and columns[0].strip() != "ITEM NO."
                and _base_pn(columns[1])
            ]
            if raw_rows:
                # Match the link parser: virtual components are "PN^parent" and
                # must resolve to the same identity here as they do in the BOM.
                root = (_base_pn(raw_rows[0][1]), clean_rev(raw_rows[0][2]))
            links = _aggregate_links(
                _parse_treebom(text, tree_names[0], diagnostics)
            )
            for ppn, prev, cpn, crev, _qty, _occurrences in links:
                parts.setdefault((ppn, prev), _shell((ppn, prev)))
                parts.setdefault((cpn, crev), _shell((cpn, crev)))
        if root:
            parts.setdefault(root, _shell(root))
        revisions_by_pn: dict[str, set[str]] = defaultdict(set)
        for pn, rev in parts:
            revisions_by_pn[pn].add(rev)
        manifest = _load_manifest(zf)
        bom_names = set(flat_names + tree_names)
        for safe, info in safe_infos.items():
            _check_archive_deadline(deadline)
            if safe in bom_names or safe in {"extra/_manifest.json", "extra/manifest.json"}:
                continue
            segments = safe.split("/")
            head = segments[0].casefold()
            if head == "bom":
                continue
            if head == "deliverables" or head in _DELIVERABLE_GROUPS:
                if head == "deliverables":
                    if len(segments) < 3:
                        raise ValueError(f"Deliverables entry missing group: {safe}")
                    group, filename_only = segments[1].casefold(), os.path.basename(segments[-1])
                else:
                    group, filename_only = head, os.path.basename(segments[-1])
                if group not in _DELIVERABLE_GROUPS:
                    raise ValueError(f"Unknown deliverables group: {group}")
                extension = _validate_deliverable_extension(group, filename_only)
                identity = _deliverable_identity(filename_only)
                if identity:
                    pn, rev, drawing = identity
                elif group == "datasheet":
                    matches = [
                        key
                        for key, part in parts.items()
                        if os.path.basename(
                            str(
                                next(
                                    (
                                        value
                                        for raw_key, value in part["attrs"].items()
                                        if canonical_attr_key(raw_key) == "datasheet"
                                    ),
                                    "",
                                )
                            )
                        ).casefold()
                        == filename_only.casefold()
                    ]
                    if len(matches) != 1:
                        diagnostics["warnings"].append(
                            {
                                "severity": "warning",
                                "stage": "files.identity",
                                "message": f"Could not resolve datasheet owner: {safe}",
                            }
                        )
                        continue
                    (pn, rev), drawing = matches[0], False
                else:
                    diagnostics["warnings"].append(
                        {
                            "severity": "warning",
                            "stage": "files.identity",
                            "message": f"Could not resolve deliverable owner: {safe}",
                        }
                    )
                    continue
                if not _claim_pair(parts, (pn, rev), safe, diagnostics):
                    continue
                content = zf.read(info)
                files.append(
                    {
                        "kind": "managed",
                        "pair": (pn, rev),
                        "identity": (group, extension, bool(drawing) if group == "png" else False),
                        "name": filename_only,
                        "relative_path": f"{group}/{filename_only}",
                        "bytes": content,
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                )
                continue
            if head == "extra":
                if not options.get("allow_extra", True):
                    diagnostics["warnings"].append(
                        {
                            "severity": "warning",
                            "stage": "files.extra",
                            "message": "Associated files disabled by configuration.",
                        }
                    )
                    continue
                if len(segments) < 3:
                    raise ValueError(f"Associated file entry missing part number: {safe}")
                pn = _base_pn(segments[1])
                if len(segments) >= 4:
                    rev, filename_only = clean_rev(rev_from_token(segments[2])), segments[-1]
                else:
                    revisions = revisions_by_pn.get(pn, set())
                    rev = next(iter(revisions)) if len(revisions) == 1 else ""
                    filename_only = segments[-1]
                filename_only = validated_upload_filename(filename_only)
                if not _claim_pair(parts, (pn, rev), safe, diagnostics):
                    continue
                relative = extra_rel_path(pn, rev, filename_only)
                content = zf.read(info)
                meta = manifest.get((pn, rev, filename_only.casefold()), {})
                files.append(
                    {
                        "kind": "associated",
                        "pair": (pn, rev),
                        "identity": relative.casefold(),
                        "name": filename_only,
                        "relative_path": relative,
                        "label": meta.get("label", ""),
                        "bytes": content,
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                )
                continue
            message = f"Unknown ZIP entry: {safe}"
            if options.get("strict_structure"):
                raise ValueError(message)
            diagnostics["warnings"].append(
                {"severity": "warning", "stage": "zip.structure", "message": message}
            )
    _validate_cycles(links)
    _resolve_duplicate_parts(parts, duplicates, options, diagnostics)
    return {
        "filename": filename,
        "parts": parts,
        "links": links,
        "files": files,
        "root": root,
        "duplicates": _duplicate_choices(duplicates),
        "diagnostics": diagnostics,
        "parse_elapsed_s": time.perf_counter() - started,
    }
def _duplicate_label(row: dict[str, Any]) -> str:
    """Human-readable origin of a duplicate row, for the operator's choice."""
    attrs = row.get("attrs") or {}
    for key in ("partnumber", "part_number", "pn"):
        raw = str(attrs.get(key) or "").strip()
        if raw:
            return raw
    return str(row.get("part_number") or "")
def _duplicate_choices(
    duplicates: dict[tuple[str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Serialisable description of every clash, one entry per identity."""
    return [
        {
            "part_number": key[0],
            "revision": key[1],
            "options": [
                {
                    "index": index,
                    "label": _duplicate_label(row),
                    "description": row.get("description") or "",
                }
                for index, row in enumerate(rows)
            ],
        }
        for key, rows in sorted(duplicates.items())
    ]
def _resolve_duplicate_parts(
    parts: dict[tuple[str, str], dict[str, Any]],
    duplicates: dict[tuple[str, str], list[dict[str, Any]]],
    options: dict[str, Any],
    diagnostics: dict[str, Any],
) -> None:
    """Apply the operator's pick for each clashing identity.

    Without a choice the first row stays (a stable, predictable default) and the
    clash is reported as a warning so the import proceeds rather than failing.
    """
    picks = options.get("duplicate_choices") or {}
    for key, rows in duplicates.items():
        chosen = 0
        raw = picks.get(f"{key[0]}␟{key[1]}", picks.get(key[0]))
        try:
            candidate = int(raw)
        except (TypeError, ValueError):
            candidate = 0
        if 0 <= candidate < len(rows):
            chosen = candidate
        parts[key] = rows[chosen]
        diagnostics["warnings"].append(
            {
                "severity": "warning",
                "stage": "flatbom.duplicate",
                "part_number": key[0],
                "revision": key[1],
                "message": (
                    f"{len(rows)} rows share this part number; kept "
                    f"“{_duplicate_label(rows[chosen])}”."
                ),
                "detail": ", ".join(_duplicate_label(row) for row in rows),
            }
        )
def _validate_cycles(
    links: Iterable[tuple[str, str, str, str, float, list[dict[str, Any]]]],
) -> None:
    graph: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for ppn, prev, cpn, crev, _qty, _occurrences in links:
        graph[(ppn, prev)].add((cpn, crev))
    visiting: set[tuple[str, str]] = set()
    visited: set[tuple[str, str]] = set()
    def visit(node: tuple[str, str]) -> None:
        if node in visiting:
            raise ValueError(f"BOM cycle blocked at {node[0]} revision {node[1] or '(blank)'}")
        if node in visited:
            return
        visiting.add(node)
        for child in graph.get(node, set()):
            visit(child)
        visiting.remove(node)
        visited.add(node)
    for parent in graph:
        visit(parent)
def _pair_query(
    model: Any,
    pairs: Iterable[tuple[str, str]],
    pn_field: str,
    rev_field: str,
) -> list[Any]:
    query: Q | None = None
    for pn, rev in sorted(set(pairs)):
        item = Q(**{pn_field: pn, rev_field: rev})
        query = item if query is None else query | item
    return list(model.objects(query)) if query is not None else []
def load_import_state(parsed_package: dict[str, Any]) -> dict[str, Any]:
    """Load one exact batch from each import collection."""
    pairs = set(parsed_package["parts"])
    parents = {
        (link[0], link[1])
        for link in parsed_package["links"]
    }
    parts = {
        (part.part_number, clean_rev(part.revision)): part
        for part in _pair_query(Part, pairs, "part_number", "revision")
    }
    boms: dict[tuple[str, str], list[BOMLink]] = defaultdict(list)
    for link in _pair_query(BOMLink, parents, "parent_pn", "parent_rev"):
        boms[(link.parent_pn, clean_rev(link.parent_rev))].append(link)
    managed: dict[tuple[tuple[str, str], tuple[str, str, bool]], PartFile] = {}
    for item in _pair_query(PartFile, pairs, "part_number", "revision"):
        managed[
            (
                (item.part_number, clean_rev(item.revision)),
                (item.ext_group.casefold(), item.ext.casefold(), bool(item.is_dwg)),
            )
        ] = item
    associated: dict[tuple[tuple[str, str], str], PartExtraFile] = {}
    for item in _pair_query(PartExtraFile, pairs, "part_number", "revision"):
        associated[
            ((item.part_number, clean_rev(item.revision)), item.rel_path.casefold())
        ] = item
    return {
        "parts": parts,
        "boms": dict(boms),
        "managed": managed,
        "associated": associated,
        "query_count": 4,
    }
def _resolve_approval(attrs: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Resolve approval through the request-cached alias snapshot when possible.

    ``build_import_plan`` seeds the runtime snapshot from the request's field
    configuration exactly once, so per-part resolution does not re-sanitise
    the alias configuration.
    """
    if has_app_context():
        return resolve_approval(attrs)
    return resolve_approval(attrs, config=config)
def _field_maps(config: dict[str, Any]) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    aliases = canonical_alias_index(config)
    fields = field_index(config)
    for field_id, field in fields.items():
        source = str(field.get("source_path") or "")
        if source.startswith("attrs."):
            aliases.setdefault(canonical_attr_key(source.split(".", 1)[1]), field_id)
        aliases.setdefault(canonical_attr_key(field_id), field_id)
    return aliases, fields
def _logical_incoming(
    normalized: dict[str, Any],
    aliases: dict[str, str],
    fields: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    attrs = normalized.get("attrs") or {}
    for raw_key, value in attrs.items():
        normalized_key = canonical_attr_key(raw_key)
        if normalized_key in _IDENTITY_KEYS:
            continue
        field_id = aliases.get(normalized_key, normalized_key)
        if field_id in _APPROVAL_FIELDS:
            continue
        if field_id in values:
            if values[field_id]["value"] != value:
                if field_id == "process":
                    # Process is multi-value: extra aliases contribute values.
                    values[field_id].setdefault("raw_values", {})[str(raw_key)] = value
                else:
                    values[field_id].setdefault("conflicts", {})[str(raw_key)] = value
            else:
                # Duplicate alias with an equal value consolidates silently.
                values[field_id].setdefault("raw_values", {})[str(raw_key)] = value
            continue
        field = fields.get(field_id) or {}
        values[field_id] = {
            "field_id": field_id,
            "label": field.get("label") or str(raw_key),
            "source_key": str(raw_key),
            "value": value,
            "write_key": (
                str(field.get("source_path")).split(".", 1)[1]
                if str(field.get("source_path") or "").startswith("attrs.")
                else field_id
            ),
            "top_level": _TOP_LEVEL_FIELDS.get(field_id),
            "raw_values": {str(raw_key): value},
        }
    for field_id, attribute in _TOP_LEVEL_FIELDS.items():
        value = normalized.get(attribute)
        if _has_value(value) and field_id not in values:
            field = fields.get(field_id) or {}
            values[field_id] = {
                "field_id": field_id,
                "label": field.get("label") or field_id.replace("_", " ").title(),
                "source_key": attribute,
                "value": value,
                "write_key": field_id,
                "top_level": attribute,
            }
    return values
def _existing_logical(
    part: Part | None,
    incoming: dict[str, Any],
    aliases: dict[str, str],
) -> Any:
    if part is None:
        return None
    if incoming.get("top_level"):
        return getattr(part, incoming["top_level"], None)
    field_id = incoming["field_id"]
    for raw_key, value in (part.attrs or {}).items():
        if aliases.get(canonical_attr_key(raw_key), canonical_attr_key(raw_key)) == field_id:
            return value
    return (part.canonical or {}).get(field_id)
def _property_action(
    mode: str,
    state: str,
    before: Any,
    after: Any,
) -> tuple[str, str]:
    if before == after:
        return "unchanged", "Incoming and existing values match."
    # Skip is checked before the new-part shortcut: selecting "Skip" must mean
    # no property is written, on a new part as much as an existing one.
    if mode == "skip":
        return "skipped", "Properties policy is Skip."
    if state == "new":
        return "add", "New part/revision."
    if mode == "fill_blanks":
        # "Fill only" promises approved parts are never touched, so a blank
        # field on an approved target is preserved rather than filled.
        if state == "existing_approved":
            return "blocked", "Fill only does not alter approved targets."
        return (
            ("add", "Existing value is blank.")
            if not _has_value(before)
            else ("skipped", "Fill blanks preserves the existing nonblank value.")
        )
    if mode == "replace_unapproved" and state == "existing_approved":
        return "blocked", "Replace unapproved does not alter approved targets."
    return "replace", "Selected property policy permits replacement."
def _approval_rows(
    part: Part | None,
    incoming_attrs: dict[str, Any],
    state: str,
    mode: str,
    config: dict[str, Any],
    aliases: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    existing = _resolve_approval(part.attrs or {}, config) if part else {
        "approved": False,
        "approved_by": "",
        "approved_date": "",
    }
    incoming = _resolve_approval(incoming_attrs, config)
    warnings = list(incoming.get("ambiguous") or [])
    rows = []
    labels = {
        APPROVED_FIELD_ID: "Approved",
        APPROVED_BY_FIELD_ID: "Approved By",
        APPROVED_DATE_FIELD_ID: "Approval Date",
    }
    values = {
        APPROVED_FIELD_ID: (bool(existing.get("approved")), bool(incoming.get("approved"))),
        APPROVED_BY_FIELD_ID: (existing.get("approved_by") or "", incoming.get("approved_by") or ""),
        APPROVED_DATE_FIELD_ID: (existing.get("approved_date") or "", incoming.get("approved_date") or ""),
    }
    has_signal = bool(incoming.get("has_approval_signal") or incoming.get("approved_date"))
    raw_existing_keys = {
        canonical_attr_key(key)
        for key in ((part.attrs or {}) if part else {})
    }
    canonical_approval_keys = {
        APPROVED_FIELD_ID,
        APPROVED_BY_FIELD_ID,
        APPROVED_DATE_FIELD_ID,
    }
    has_legacy_existing_alias = bool(
        raw_existing_keys
        and any(
            aliases.get(key) in _APPROVAL_FIELDS and key not in canonical_approval_keys
            for key in raw_existing_keys
        )
    )
    for field_id, (before, after) in values.items():
        if not has_signal:
            if has_legacy_existing_alias and _has_value(before):
                action, reason = "change", "Normalise the existing configured approval alias."
                after = before
            else:
                action, reason = "unchanged", "No incoming approval value."
        elif warnings:
            action, reason = "blocked", "Incoming approval aliases conflict."
            after = before
        elif before == after:
            action, reason = "unchanged", "Incoming and existing values match."
        elif mode == "skip":
            action, reason = "skipped", "Properties policy is Skip."
            after = before
        elif state == "new":
            # There is no existing approval to preserve on a new target, so
            # recording the incoming signal is not a modification. Any uploader
            # may create approved data; only changing it later is restricted.
            action, reason = "add", "Approval signal recorded on the new target."
        elif mode == "preserve":
            action, reason = "skipped", "Approval policy preserves existing approval fields."
            after = before
        elif mode == "import_unapproved" and state == "existing_approved":
            action, reason = "blocked", "Import unapproved does not alter approved targets."
            after = before
        else:
            action = "clear" if not _has_value(after) else ("add" if not _has_value(before) else "change")
            reason = "Selected approval policy permits this change."
        rows.append(
            {
                "field_id": field_id,
                "label": labels[field_id],
                "source_key": (
                    incoming.get("status_source")
                    if field_id == APPROVED_FIELD_ID
                    else incoming.get("identity_source")
                    if field_id == APPROVED_BY_FIELD_ID
                    else incoming.get("date_source")
                )
                or field_id,
                "before": _json_value(before),
                "after": _json_value(after),
                "action": action,
                "reason": reason,
            }
        )
    return rows, warnings
def _bom_redline(
    incoming: dict[tuple[str, str], float],
    existing_links: list[BOMLink],
    state: str,
    mode: str,
) -> dict[str, Any]:
    existing = {
        (link.child_pn, clean_rev(link.child_rev)): float(link.qty or 0)
        for link in existing_links
    }
    changes = []
    for child in sorted(set(existing) | set(incoming)):
        before, after = existing.get(child), incoming.get(child)
        if before == after:
            action = "unchanged"
        elif before is None:
            action = "add"
        elif after is None:
            action = "remove"
        else:
            action = "quantity_change"
        changes.append(
            {
                "part_number": child[0],
                "revision": child[1],
                "before_qty": before,
                "after_qty": after,
                "action": action,
            }
        )
    changed = any(item["action"] != "unchanged" for item in changes)
    if not changed:
        action, reason = "unchanged", "Incoming and existing BOMs match."
    elif mode == "skip":
        action, reason = "skipped", "BOM policy preserves the existing definition."
    elif mode == "fill_if_empty" and state == "existing_approved":
        # "Fill only" promises approved parts are never touched.
        action, reason = "blocked", "Fill only does not alter approved targets."
    elif mode == "fill_if_empty" and existing:
        action, reason = "skipped", "Fill if empty never merges into an existing BOM."
    elif mode == "replace_unapproved" and state == "existing_approved":
        action, reason = "blocked", "Replace unapproved does not alter an approved parent."
    else:
        action = "add" if not existing else "replace"
        reason = "Selected BOM policy permits this exact-parent change."
    if action in {"skipped", "blocked"}:
        for item in changes:
            if item["action"] != "unchanged":
                item["planned_action"] = item["action"]
                item["action"] = action
    return {"action": action, "reason": reason, "changes": changes}
def _file_action(
    mode: str,
    state: str,
    exists: bool,
    same: bool,
) -> tuple[str, str]:
    if exists and same:
        return "unchanged", "File content matches."
    if mode == "skip":
        return "skipped", "Files policy is Skip."
    if mode == "add_missing" and state == "existing_approved":
        # "Fill only" promises approved parts are never touched.
        return "blocked", "Fill only does not alter approved targets."
    if not exists:
        return "add", "No equivalent file identity exists."
    if mode == "add_missing":
        return "skipped", "Add missing never overwrites an existing file identity."
    if mode == "replace_unapproved" and state == "existing_approved":
        return "blocked", "Replace unapproved does not alter approved targets."
    return "replace", "Selected file policy permits replacement."
def _discovered_file_rows(
    pair: tuple[str, str],
    existing_part: Part | None,
    existing_state: dict[str, Any],
    incoming_attrs: dict[str, Any],
) -> list[dict[str, Any]]:
    """Redline rows for files found in storage rather than carried in the ZIP.

    Record reconciliation is not gated by the file policy: it only points
    ``PartFile`` at bytes that already exist on disk, so it neither writes nor
    overwrites content. Discovery resolves datasheet aliases against the attrs
    the part will hold after the import, so a datasheet named by this very
    package is still found.
    """
    rows = []
    attrs = {**((existing_part.attrs if existing_part else None) or {}), **(incoming_attrs or {})}
    for (group, drawing), record in discover_part_files(*pair, attrs=attrs).items():
        extension = str(record.get("ext") or "").casefold()
        existing_file = existing_state["managed"].get((pair, (group.casefold(), extension, drawing)))
        linked = bool(existing_file) and getattr(existing_file, "rel_path", "") == record.get("rel_path")
        rows.append(
            {
                "kind": "discovered",
                "name": os.path.basename(str(record.get("rel_path") or "")),
                "category": group,
                "action": "unchanged" if linked else ("link" if existing_file else "add"),
                "reason": (
                    "Storage file is already recorded."
                    if linked
                    else "Found in storage; the file record is repointed."
                    if existing_file
                    else "Found in storage; a file record is created."
                ),
                "_discovered": {"ext_group": group, "is_dwg": drawing, **record},
            }
        )
    return rows
def build_import_plan(
    parsed_package: dict[str, Any],
    existing_state: dict[str, Any],
    options: dict[str, Any],
    field_config: dict[str, Any],
) -> dict[str, Any]:
    """Create the complete no-write redline."""
    aliases, fields = _field_maps(field_config)
    if has_app_context():
        # Seed the request-scoped alias/approval snapshot exactly once so all
        # per-part approval resolution reuses it.
        set_runtime_canonical_aliases(field_config)
    incoming_boms: dict[tuple[str, str], dict[tuple[str, str], float]] = defaultdict(dict)
    for ppn, prev, cpn, crev, qty, _occurrences in parsed_package["links"]:
        incoming_boms[(ppn, prev)][(cpn, crev)] = float(qty)
    files_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for file in parsed_package["files"]:
        files_by_pair[file["pair"]].append(file)
    entries = []
    approval_warning_count = 0
    for pair, normalized in sorted(parsed_package["parts"].items()):
        existing_part = existing_state["parts"].get(pair)
        existing_approval = (
            _resolve_approval(existing_part.attrs or {}, field_config)
            if existing_part
            else {"approved": False, "ambiguous": []}
        )
        state = (
            "new"
            if existing_part is None
            else "existing_approved"
            if existing_approval.get("approved")
            else "existing_unapproved"
        )
        properties = []
        for field_id, incoming in sorted(_logical_incoming(normalized, aliases, fields).items()):
            before = _existing_logical(existing_part, incoming, aliases)
            action, reason = _property_action(
                options["data_mode"],
                state,
                before,
                incoming["value"],
            )
            conflicts = incoming.get("conflicts") or {}
            if conflicts:
                reason = (
                    f"{reason} Conflicting duplicate aliases kept the first value "
                    f"({incoming['source_key']}); ignored: "
                    + ", ".join(sorted(conflicts))
                    + "."
                )
            properties.append(
                {
                    "field_id": field_id,
                    "label": incoming["label"],
                    "source_key": incoming["source_key"],
                    "write_key": incoming["write_key"],
                    "top_level": incoming["top_level"],
                    "raw_values": incoming.get("raw_values", {}),
                    "alias_conflicts": _json_value(conflicts),
                    "before": _json_value(before),
                    "after": _json_value(incoming["value"]),
                    "action": action,
                    "reason": reason,
                }
            )
        approval, approval_warnings = _approval_rows(
            existing_part,
            normalized.get("attrs") or {},
            state,
            # Approval values live in attrs, so skipping properties skips them.
            "skip" if options["data_mode"] == "skip" else options["approval_mode"],
            field_config,
            aliases,
        )
        approval_warning_count += len(approval_warnings)
        for warning in approval_warnings:
            parsed_package["diagnostics"]["warnings"].append(
                {
                    "severity": "warning",
                    "stage": "flatbom.approval",
                    "part_number": pair[0],
                    "revision": pair[1],
                    "message": "Incoming approval aliases conflict; approval changes were blocked.",
                    "detail": warning,
                }
            )
        bom = _bom_redline(
            incoming_boms.get(pair, {}),
            existing_state["boms"].get(pair, []),
            state,
            options["bom_mode"],
        ) if pair in incoming_boms else {
            "action": "unchanged",
            "reason": "No incoming BOM definition.",
            "changes": [],
        }
        file_rows = []
        for file in files_by_pair.get(pair, []):
            if file["kind"] == "managed":
                existing_file = existing_state["managed"].get((pair, file["identity"]))
            else:
                existing_file = existing_state["associated"].get((pair, file["identity"]))
            same = bool(existing_file and getattr(existing_file, "sha256", "") == file["sha256"])
            action, reason = _file_action(
                options["file_mode"],
                state,
                existing_file is not None,
                same,
            )
            file_rows.append(
                {
                    "kind": file["kind"],
                    "name": file["name"],
                    "category": file["identity"][0] if file["kind"] == "managed" else "associated",
                    "action": action,
                    "reason": reason,
                    "_file": file,
                }
            )
        # BOM-only packs carry no deliverables; their files already sit in
        # storage. Plan the same reconciliation the apply performs so the
        # redline reports discovered files instead of showing none. The Files
        # policy still governs it: "Skip" means the storage scan is not run at
        # all, so no file records are touched.
        if not parsed_package["files"] and options["file_mode"] != "skip":
            file_rows.extend(
                _discovered_file_rows(
                    pair, existing_part, existing_state, normalized.get("attrs") or {}
                )
            )
        changed_actions = {"add", "replace", "remove", "quantity_change", "change", "clear"}
        # Discovered rows only reconcile file records, so they are reported but
        # never make the part itself count as changed.
        content_files = [item for item in file_rows if item["kind"] != "discovered"]
        blocked_count = sum(
            item["action"] == "blocked"
            for item in properties + approval + content_files
        ) + int(bom["action"] == "blocked")
        changed = (
            any(item["action"] in changed_actions for item in properties + approval + content_files)
            or bom["action"] in {"add", "replace"}
        )
        entries.append(
            {
                "part_number": pair[0],
                "revision": pair[1],
                "target_state": state,
                "properties": properties,
                "approval": approval,
                "approval_integrity_warnings": approval_warnings,
                "bom": bom,
                "files": file_rows,
                "changed": changed,
                "blocked": blocked_count > 0,
                "blocked_change_count": blocked_count,
            }
        )
    plan = {
        "parts": entries,
        "options": {
            key: options[key]
            for key in ("data_mode", "bom_mode", "file_mode", "approval_mode")
        },
        "approval_integrity_warnings": approval_warning_count,
        "_parsed": parsed_package,
        "_state": existing_state,
        "_config": field_config,
        "_options": options,
    }
    required_import_permissions(plan)
    return plan
def required_import_permissions(plan: dict[str, Any]) -> list[str]:
    """Derive every permission the completed plan requires.

    This is the single authority consumed by the API route and, through the
    plan payload, by the React UI. It combines the import execution tier
    (low-risk, advanced, approved override) with the resource write
    permissions implied by the planned effects, so import execution never
    implicitly grants Part, BOM or file writes and vice versa.
    """
    changed_actions = {"add", "replace", "change", "clear"}
    destructive_actions = {"replace", "change", "clear"}
    existing_pairs = set(plan["_state"]["parts"])
    required: set[str] = set()
    low_risk = False
    advanced = False
    approved_override = False
    for part in plan["parts"]:
        state = part["target_state"]
        property_actions = {
            item["action"]
            for item in part["properties"] + part["approval"]
        } & changed_actions
        content = [item for item in part["files"] if item["kind"] != "discovered"]
        file_adds = any(item["action"] == "add" for item in content)
        file_replaces = any(item["action"] == "replace" for item in content)
        bom_action = part["bom"]["action"]
        bom_changed = bom_action in {"add", "replace"}
        if not (property_actions or file_adds or file_replaces or bom_changed):
            continue
        if state == "new":
            required.add("parts.create")
        elif property_actions:
            required.add("parts.update")
        if bom_changed:
            required.add("bom.update")
            # Writing the BOM materialises any child that does not exist yet,
            # so the same rows demand the create capability.
            if any(
                (link[2], link[3]) not in existing_pairs
                for link in plan["_parsed"]["links"]
                if (link[0], link[1]) == (part["part_number"], part["revision"])
            ):
                required.add("parts.create")
        if file_adds:
            required.add("files.add")
        if file_replaces:
            required.add("files.replace")
        if state == "existing_approved":
            advanced = approved_override = True
        elif state == "existing_unapproved" and (
            property_actions & destructive_actions
            or file_replaces
            or bom_action == "replace"
        ):
            advanced = True
        else:
            low_risk = True
    if not (low_risk or advanced or approved_override):
        # A plan with zero effects is still an execution request whose response
        # discloses plan details, so it must not bypass the import tiers.
        low_risk = True
    if low_risk:
        required.add("imports.execute_low_risk")
    if advanced:
        required.add("imports.execute_approved")
    if approved_override:
        required.add("imports.override_approved")
    plan["required_permissions"] = sorted(required)
    return plan["required_permissions"]
def _public_plan(
    plan: dict[str, Any],
    *,
    actor_permissions: set[str] | None,
) -> dict[str, Any]:
    permissions = set(actor_permissions or ())
    missing = (
        sorted(set(plan["required_permissions"]) - permissions)
        if actor_permissions is not None
        else []
    )
    parts = []
    for entry in plan["parts"]:
        row = {
            key: _json_value(value)
            for key, value in entry.items()
            if not key.startswith("_")
        }
        row["files"] = [
            {key: _json_value(value) for key, value in item.items() if not key.startswith("_")}
            for item in entry["files"]
        ]
        row["allowed"] = not bool(missing) and not row["blocked"]
        parts.append(row)
    return {
        "parts": parts,
        "options": dict(plan["options"]),
        "required_permissions": list(plan["required_permissions"]),
        "missing_permissions": missing,
        "allowed": not missing,
        "blocked_change_count": sum(item["blocked_change_count"] for item in parts),
        "approval_integrity_warnings": plan["approval_integrity_warnings"],
        # Identity clashes the operator can re-resolve by re-running with a pick.
        "duplicates": list(plan["_parsed"].get("duplicates") or []),
        "summary": {
            "parts": len(parts),
            "new": sum(item["target_state"] == "new" for item in parts),
            "changed": sum(bool(item["changed"]) for item in parts),
            "blocked": sum(bool(item["blocked"]) for item in parts),
            # Approved parts the import actually alters — the case worth
            # reviewing, unlike the count of approved parts merely touched.
            "modified_approved": sum(
                item["target_state"] == "existing_approved" and bool(item["changed"])
                for item in parts
            ),
        },
    }
def _apply_properties(part: Part, entry: dict[str, Any], aliases: dict[str, str]) -> None:
    attrs = normalize_record_attrs(dict(part.attrs or {}))
    for change in entry["properties"]:
        if change["action"] not in {"add", "replace"}:
            continue
        field_id = change["field_id"]
        if field_id == "process":
            for raw_key, value in change.get("raw_values", {}).items():
                attrs[raw_key] = value
            continue
        if field_id in aliases.values():
            attrs = {
                key: value
                for key, value in attrs.items()
                if aliases.get(canonical_attr_key(key), canonical_attr_key(key)) != field_id
            }
        if change.get("top_level"):
            setattr(part, change["top_level"], change["after"])
        attrs[change["write_key"]] = change["after"]
    part.attrs = attrs
def _apply_approval(part: Part, entry: dict[str, Any], aliases: dict[str, str]) -> None:
    changes = {
        item["field_id"]: item
        for item in entry["approval"]
        if item["action"] in {"add", "change", "clear"}
    }
    if not changes:
        return
    attrs = {
        key: value
        for key, value in (part.attrs or {}).items()
        if aliases.get(canonical_attr_key(key), canonical_attr_key(key)) not in _APPROVAL_FIELDS
    }
    for field_id, change in changes.items():
        if change["action"] != "clear":
            attrs[field_id] = change["after"]
    part.attrs = normalize_record_attrs(attrs)
def _file_coverage(
    plan: dict[str, Any],
    pair: tuple[str, str],
) -> set[str]:
    groups = {
        identity[0]
        for (file_pair, identity), _document in plan["_state"]["managed"].items()
        if file_pair == pair
    }
    for entry in plan["parts"]:
        if (entry["part_number"], entry["revision"]) != pair:
            continue
        for item in entry["files"]:
            if item["kind"] == "discovered":
                groups.add(item["category"])
            elif item["kind"] == "managed" and item["action"] in {"add", "replace"}:
                groups.add(item["_file"]["identity"][0])
    return groups
def _make_stage_root(file_root: str | None = None) -> str:
    """A staging directory ON THE SAME FILESYSTEM as the files being written.

    _commit_files finishes with os.replace, which is atomic but CANNOT cross a
    filesystem boundary - it raises EXDEV. The hardened container runs with a
    read-only root and a tmpfs /tmp, so the system temp dir is a different
    device from the bind-mounted deliverables volume, and every import that
    wrote a file failed with "cross-store file commit failed".

    Staging inside the deliverables root keeps the commit atomic instead of
    trading it for a copy, which would leave a truncated file behind on a
    partial write. The dot prefix keeps it out of the way of file scans, and
    the caller removes it in a finally block.

    Falls back to the system temp dir when there is no file root, which is the
    case for imports that write no files and therefore never commit any.
    """
    if file_root:
        try:
            os.makedirs(file_root, exist_ok=True)
            return tempfile.mkdtemp(prefix=".tinymrp-import-", dir=file_root)
        except OSError:
            # An unwritable deliverables root is a real problem, but it is the
            # commit's problem to report - not a reason to fail here.
            logger.warning("could not stage inside %s; falling back to temp", file_root, exc_info=True)
    return tempfile.mkdtemp(prefix="tinymrp-import-")


def _stage_files(plan: dict[str, Any], file_root: str) -> tuple[str, list[dict[str, Any]]]:
    stage_root = _make_stage_root(file_root)
    staged = []
    try:
        for entry in plan["parts"]:
            pair = (entry["part_number"], entry["revision"])
            for row in entry["files"]:
                if row["action"] not in {"add", "replace"} or "_file" not in row:
                    continue
                file = row["_file"]
                destination = _safe_destination(file_root, file["relative_path"])
                stage_path = os.path.join(stage_root, str(len(staged)))
                with open(stage_path, "wb") as handle:
                    handle.write(file["bytes"])
                if hashlib.sha256(Path(stage_path).read_bytes()).hexdigest() != file["sha256"]:
                    raise ValueError(f"staged file checksum failed for {pair[0]} revision {pair[1]}")
                staged.append(
                    {
                        "pair": pair,
                        "row": row,
                        "file": file,
                        "stage_path": stage_path,
                        "destination": destination,
                    }
                )
        return stage_root, staged
    except Exception:
        shutil.rmtree(stage_root, ignore_errors=True)
        raise
def _commit_files(stage_root: str, staged: list[dict[str, Any]]) -> None:
    backup_root = os.path.join(stage_root, "backups")
    committed: list[dict[str, Any]] = []
    try:
        for index, item in enumerate(staged):
            os.makedirs(os.path.dirname(item["destination"]), exist_ok=True)
            backup = ""
            if os.path.exists(item["destination"]):
                os.makedirs(backup_root, exist_ok=True)
                backup = os.path.join(backup_root, str(index))
                os.replace(item["destination"], backup)
            item["backup"] = backup
            os.replace(item["stage_path"], item["destination"])
            committed.append(item)
    except Exception as exc:
        for item in reversed(committed):
            try:
                if os.path.exists(item["destination"]):
                    os.remove(item["destination"])
                if item.get("backup"):
                    os.replace(item["backup"], item["destination"])
            except OSError:
                pass
        pair = item.get("pair", ("unknown", "")) if "item" in locals() else ("unknown", "")
        raise RuntimeError(
            f"cross-store file commit failed at {pair[0]} revision {pair[1] or '(blank)'}"
        ) from exc
def _write_boms(plan: dict[str, Any]) -> int:
    deletes = []
    inserts = []
    parsed_links: dict[tuple[str, str], list[tuple[Any, ...]]] = defaultdict(list)
    for link in plan["_parsed"]["links"]:
        parsed_links[(link[0], link[1])].append(link)
    for entry in plan["parts"]:
        if entry["bom"]["action"] not in {"add", "replace"}:
            continue
        pair = (entry["part_number"], entry["revision"])
        deletes.append(DeleteMany({"parent_pn": pair[0], "parent_rev": pair[1]}))
        for ppn, prev, cpn, crev, qty, occurrences in parsed_links.get(pair, []):
            inserts.append(
                InsertOne(
                    {
                        "parent_pn": ppn,
                        "parent_rev": prev,
                        "child_pn": cpn,
                        "child_rev": crev,
                        "qty": qty,
                        "uom": "EA",
                        "occurrences": occurrences,
                        "updated_at": utc_now(),
                    }
                )
            )
    collection = BOMLink._get_collection()
    if deletes:
        collection.bulk_write(deletes, ordered=True)
    if inserts:
        collection.bulk_write(inserts, ordered=True)
    return len(inserts)
def _write_file_metadata(staged: list[dict[str, Any]], uploaded_by: str, seed_tag: str) -> None:
    managed_ops = []
    associated_ops = []
    now = utc_now()
    for item in staged:
        file = item["file"]
        pn, rev = item["pair"]
        stat = os.stat(item["destination"])
        if file["kind"] == "managed":
            group, extension, drawing = file["identity"]
            managed_ops.append(
                UpdateOne(
                    {
                        "part_number": pn,
                        "revision": rev,
                        "ext_group": group,
                        "ext": extension,
                        "is_dwg": drawing,
                    },
                    {
                        "$set": {
                            "rel_path": file["relative_path"],
                            "path": item["destination"],
                            "size": float(stat.st_size),
                            "mtime_iso": now,
                            "sha256": file["sha256"],
                            "content_type": mimetypes.guess_type(file["name"])[0]
                            or "application/octet-stream",
                            "source": seed_tag,
                            "discovered_at": now,
                        }
                    },
                    upsert=True,
                )
            )
        else:
            associated_ops.append(
                UpdateOne(
                    {"part_number": pn, "revision": rev, "rel_path": file["relative_path"]},
                    {
                        "$set": {
                            "original_name": file["name"],
                            "size": float(stat.st_size),
                            "mime": mimetypes.guess_type(file["name"])[0]
                            or "application/octet-stream",
                            "sha256": file["sha256"],
                            "label": file.get("label", ""),
                            "uploaded_by": uploaded_by,
                            "uploaded_at": now,
                            "source": seed_tag,
                        }
                    },
                    upsert=True,
                )
            )
    _bulk_updates(PartFile._get_collection(), managed_ops)
    _bulk_updates(PartExtraFile._get_collection(), associated_ops)
def _bulk_updates(collection: Any, operations: list[UpdateOne]) -> None:
    if not operations:
        return
    try:
        collection.bulk_write(operations, ordered=True)
    except TypeError:
        # mongomock currently lags pymongo's UpdateOne signature.  Production
        # uses the single bulk call; tests retain equivalent atomic upserts.
        if not collection.__class__.__module__.startswith("mongomock"):
            raise
        for operation in operations:
            collection.update_one(
                operation._filter,
                operation._doc,
                upsert=operation._upsert,
            )
def import_idempotency_key(file_bytes: bytes, options: dict[str, Any]) -> str:
    """Fingerprint a pack plus the policies it will run under.

    The same bytes imported with different modes is a DIFFERENT operation - a
    fill-blanks run and a replace-all run touch different data - so the policy
    options are part of the key, not just the archive.

    Used to recognise a repeat, not to block one: re-importing deliberately is
    legitimate, so the caller decides what to do with the answer.
    """
    digest = hashlib.sha256(file_bytes).hexdigest()
    policy = "|".join(
        f"{key}={options.get(key, '')}"
        for key in ("data_mode", "bom_mode", "file_mode", "approval_mode")
    )
    return hashlib.sha256(f"{digest}|{policy}".encode()).hexdigest()


def previous_successful_import(key: str) -> ImportJournal | None:
    """The last COMMITTED run of this exact pack+policy combination, if any.

    Only committed runs count. A failed or rolled-back attempt should be
    retried, which is the whole point of retrying.
    """
    if not key:
        return None
    try:
        return (
            ImportJournal.objects(idempotency_key=key, status="committed")
            .order_by("-finished_at")
            .first()
        )
    except Exception:  # pragma: no cover - journal must never break imports
        # Returning None means "no previous run found", so a failure here does
        # not just lose a record: it defeats the idempotency check and the
        # SAME IMPORT CAN RUN TWICE. The import is still allowed to proceed -
        # blocking on a journal outage would be worse - but this must be
        # visible, because a duplicate import is a data problem, not a log gap.
        logger.exception(
            "import journal lookup failed for idempotency key %s; "
            "a repeated submission will not be recognised as a duplicate",
            key,
        )
        return None


def _journal_start(
    plan: dict[str, Any],
    *,
    uploaded_by: str,
    seed_tag: str,
    idempotency_key: str = "",
) -> ImportJournal | None:
    """Open a journal entry before any effect is applied.

    Journalling must never be the reason an import fails, so every journal
    operation is best-effort: if the journal cannot be written the import still
    runs, it is simply less diagnosable.
    """
    try:
        planned_files = sum(
            1
            for entry in plan["parts"]
            for item in entry["files"]
            if item["action"] in {"add", "replace"} and "_file" in item
        )
        journal = ImportJournal(
            operation_id=uuid.uuid4().hex,
            status="started",
            stage="parts",
            uploaded_by=uploaded_by or "",
            seed_tag=seed_tag or "",
            idempotency_key=idempotency_key or "",
            planned_parts=len(plan.get("parts") or []),
            planned_files=planned_files,
        )
        journal.save()
        return journal
    except Exception:  # pragma: no cover - journal must not break imports
        return None


def _journal_update(journal: ImportJournal | None, **fields: Any) -> None:
    if journal is None:
        return
    try:
        for key, value in fields.items():
            setattr(journal, key, value)
        journal.save()
    except Exception:  # pragma: no cover - best effort
        # The journal is how an operator reconstructs a failed import, so a
        # journal write that fails SILENTLY makes it lie. Never raise into the
        # import itself - that would turn bookkeeping into data loss - but it
        # must not disappear.
        logger.exception("import journal update failed; the journal may now be stale")


def _rollback_created_parts(
    created_pairs: list[tuple[str, str]],
    journal: ImportJournal | None,
) -> None:
    """Remove parts this import brought into existence.

    Only parts CREATED by this run are removed. Parts that already existed are
    deliberately left alone: their prior field values were overwritten in place
    and are not recoverable here, so deleting them would destroy data rather
    than restore it. Those are reported for manual reconciliation instead.
    """
    actions: list[str] = []
    followup: list[str] = []
    for pn, rev in created_pairs:
        try:
            Part.objects(part_number=pn, revision=rev).delete()
            BOMLink._get_collection().delete_many({"parent_pn": pn, "parent_rev": rev})
            actions.append(f"deleted created part {pn}:{rev or '(blank)'}")
        except Exception as exc:  # pragma: no cover - defensive
            followup.append(
                f"could not remove created part {pn}:{rev or '(blank)'}: {exc}"
            )
    _journal_update(
        journal,
        status="rolled_back",
        rollback_actions=actions,
        manual_followup=followup,
        finished_at=utc_now(),
    )


def execute_import_plan(
    plan: dict[str, Any],
    *,
    uploaded_by: str = "",
    seed_tag: str = "upload-pack",
    generate_thumbs: bool = True,
    idempotency_key: str = "",
) -> dict[str, Any]:
    """Execute only effects already selected in the authorised plan."""
    runtime_config = current_app.config if has_app_context() else {}
    file_root = str(
        runtime_config.get("FILE_ROOT_LOCAL")
        or runtime_config.get("FILES_LOCAL_ROOT")
        or ""
    ).strip()
    has_file_writes = any(
        item["action"] in {"add", "replace"} and "_file" in item
        for entry in plan["parts"]
        for item in entry["files"]
    )
    if has_file_writes and not file_root:
        raise ValueError("FILE_ROOT_LOCAL not configured")
    stage_root, staged = _stage_files(plan, file_root) if has_file_writes else (
        _make_stage_root(),
        [],
    )
    aliases, _fields = _field_maps(plan["_config"])
    parts_created = 0
    parts_updated = 0
    changed_pairs: set[tuple[str, str]] = set()
    # Parts this run brings into existence. Tracked separately from
    # changed_pairs because only these can be safely removed on rollback.
    created_pairs: list[tuple[str, str]] = []
    journal = _journal_start(
        plan, uploaded_by=uploaded_by, seed_tag=seed_tag, idempotency_key=idempotency_key
    )
    try:
        # A written BOM row needs its parent and child to exist, and a stored
        # file needs its owner, even when the Properties policy is Skip. Those
        # parts are materialised as bare shells carrying no imported property.
        structural: set[tuple[str, str]] = set()
        for entry in plan["parts"]:
            pair = (entry["part_number"], entry["revision"])
            if entry["bom"]["action"] in {"add", "replace"}:
                structural.add(pair)
                structural.update(
                    (link[2], link[3])
                    for link in plan["_parsed"]["links"]
                    if (link[0], link[1]) == pair
                )
            # Discovered rows only reconcile records for files already in
            # storage; they never justify creating the part itself.
            if any(
                item["action"] in {"add", "replace"} and item["kind"] != "discovered"
                for item in entry["files"]
            ):
                structural.add(pair)
        # Only ones that do not exist yet: an existing part needs no rewrite
        # just because its BOM or files are being reconciled.
        structural -= set(plan["_state"]["parts"])

        for entry in plan["parts"]:
            pair = (entry["part_number"], entry["revision"])
            if not entry["changed"] and pair not in structural:
                continue
            part = plan["_state"]["parts"].get(pair)
            if part is None:
                part = Part(
                    part_number=pair[0],
                    revision=pair[1],
                    description="",
                    uom="EA",
                    attrs={"seed": seed_tag},
                )
                parts_created += 1
                created_pairs.append(pair)
            else:
                parts_updated += 1
            _apply_properties(part, entry, aliases)
            _apply_approval(part, entry, aliases)
            attrs = dict(part.attrs or {})
            attrs["seed"] = seed_tag
            part.attrs = normalize_record_attrs(attrs)
            sync_part_materialized_fields(
                part,
                config=plan["_config"],
                attrs=part.attrs,
                coverage=_file_coverage(plan, pair),
            )
            part.save(sync_materialized=False)
            plan["_state"]["parts"][pair] = part
            changed_pairs.add(pair)
        # Record what the database now holds before touching the filesystem.
        # If the file commit fails, this is the evidence an operator needs.
        _journal_update(
            journal,
            stage="boms",
            parts_created=parts_created,
            parts_updated=parts_updated,
            touched_parts=[f"{pn}\x1f{rev}" for pn, rev in sorted(changed_pairs)],
        )
        links_created = _write_boms(plan)
        _journal_update(journal, stage="files", links_created=links_created)
        _commit_files(stage_root, staged)
        _journal_update(journal, stage="file_metadata", files_written=len(staged))
        _write_file_metadata(staged, uploaded_by, seed_tag)
        managed_changed = {
            item["pair"]
            for item in staged
            if item["file"]["kind"] == "managed"
        }
        # BOM-only packs (the addin's Create BOM / Upload pack output) carry no
        # deliverables; the matching files already live in storage, so every
        # imported part reconciles its file records from a storage scan —
        # including re-imports whose part data is already up to date.
        records = [
            {
                "part_number": entry["part_number"],
                "revision": entry["revision"],
                **item["_discovered"],
            }
            for entry in plan["parts"]
            for item in entry["files"]
            if "_discovered" in item
        ]
        files_discovered = (
            int(upsert_part_files_detailed(records).get("count") or 0) if records else 0
        )
        thumb_pairs = managed_changed if generate_thumbs else set()
        thumbnails = generate_thumbs_for_parts(sorted(thumb_pairs)) if thumb_pairs else 0
        _journal_update(
            journal,
            status="committed",
            stage="done",
            files_written=len(staged),
            finished_at=utc_now(),
        )
        return {
            "parts_created": parts_created,
            "parts_updated": parts_updated,
            "links_created": links_created,
            "files_written": len(staged),
            "managed_files_written": sum(item["file"]["kind"] == "managed" for item in staged),
            "associated_files_written": sum(item["file"]["kind"] == "associated" for item in staged),
            "files_discovered": files_discovered,
            "thumbnails_generated": int(thumbnails or 0),
            "materialized_part_saves": len(changed_pairs),
            "operation_id": journal.operation_id if journal is not None else "",
        }
    except Exception as exc:
        # The filesystem commit rolls itself back, but the database writes above
        # it do not. Undo the parts this run created, and record everything that
        # cannot be undone so an operator can reconcile deliberately rather than
        # discovering the damage later.
        _journal_update(
            journal,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
            finished_at=utc_now(),
        )
        updated_existing = sorted(
            f"{pn}:{rev or '(blank)'}"
            for pn, rev in changed_pairs
            if (pn, rev) not in set(created_pairs)
        )
        _rollback_created_parts(created_pairs, journal)
        if updated_existing:
            _journal_update(
                journal,
                manual_followup=[
                    "pre-existing parts were modified in place and cannot be "
                    "restored automatically: " + ", ".join(updated_existing)
                ],
            )
        raise
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)
def _changed_existing_pairs(plan: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (entry["part_number"], entry["revision"])
        for entry in plan["parts"]
        if entry["changed"] and entry["target_state"] != "new"
    ]
def import_upload_pack(
    file_bytes: bytes,
    filename: str,
    *,
    uploaded_by: str = "",
    dry_run: bool = False,
    strict_structure: bool = False,
    allow_extra: bool = True,
    seed_tag: str = "upload-pack",
    data_mode: str | None = None,
    bom_mode: str | None = None,
    file_mode: str | None = None,
    approval_mode: str | None = None,
    actor_permissions: set[str] | None = None,
    scope_check: Any = None,
    generate_thumbs: bool = True,
    duplicate_choices: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse once, load once, plan once and optionally execute that plan.

    ``scope_check`` receives the exact existing ``(part_number, revision)``
    pairs the plan mutates and returns the subset outside the caller's
    mutable scope; a non-empty result blocks the apply.

    ``duplicate_choices`` maps a clashing ``"part_number␟revision"`` to the
    index of the row to keep; unspecified clashes keep the first row.
    """
    started = time.perf_counter()
    options = _policy_options(
        data_mode=data_mode,
        bom_mode=bom_mode,
        file_mode=file_mode,
        approval_mode=approval_mode,
    )
    options.update(
        {
            "strict_structure": strict_structure,
            "allow_extra": allow_extra,
            "duplicate_choices": duplicate_choices or {},
        }
    )
    parsed = parse_import_package(file_bytes, filename, options)
    state = load_import_state(parsed)
    config = get_field_config()
    plan = build_import_plan(parsed, state, options, config)
    public = _public_plan(plan, actor_permissions=actor_permissions)
    if actor_permissions is not None:
        preview_missing = {"imports.preview"} - set(actor_permissions)
        if dry_run and preview_missing:
            raise ImportPermissionError(preview_missing)
        if not dry_run and public["missing_permissions"]:
            raise ImportPermissionError(public["missing_permissions"])
    if not dry_run and scope_check is not None:
        mutated = _changed_existing_pairs(plan)
        denied = list(scope_check(mutated)) if mutated else []
        if denied:
            raise ImportScopeError(denied)
    # IMPORT-ATOMIC-01: recognise a repeat so an operator retrying after a
    # failure can see the pack already landed, instead of silently importing it
    # twice. Reported, never enforced - a deliberate re-import is legitimate.
    idempotency_key = import_idempotency_key(file_bytes, options)
    previous = previous_successful_import(idempotency_key)

    metrics: dict[str, Any] = {}
    if not dry_run:
        metrics = execute_import_plan(
            plan,
            uploaded_by=uploaded_by,
            seed_tag=seed_tag,
            generate_thumbs=generate_thumbs,
            idempotency_key=idempotency_key,
        )
    elapsed = time.perf_counter() - started
    capabilities = {
        permission: actor_permissions is None or permission in actor_permissions
        for permission in sorted(IMPORT_PERMISSIONS)
    }
    root = parsed["root"] or ("", "")
    return {
        "zip": filename,
        "dry_run": bool(dry_run),
        "idempotency_key": idempotency_key,
        # Set when this exact pack+policy combination already committed. The UI
        # can warn "this looks like a repeat"; nothing is blocked.
        "previously_imported_operation_id": (previous.operation_id if previous else ""),
        "previously_imported_at": (
            previous.finished_at.isoformat() if previous and previous.finished_at else ""
        ),
        "root": root[0],
        "root_rev": root[1],
        # Preview-only image of the top level part, inline so it needs no
        # storage and disappears with the response.
        "root_preview": _root_preview_data_uri(parsed["files"], parsed["root"]),
        "options": public["options"],
        "plan": public,
        "required_permissions": public["required_permissions"],
        "missing_permissions": public["missing_permissions"],
        "allowed": public["allowed"],
        "blocked_change_count": public["blocked_change_count"],
        "capabilities": capabilities,
        "warnings": parsed["diagnostics"]["warnings"],
        "errors": parsed["diagnostics"]["errors"],
        "metrics": metrics,
        "timings": {
            "parse_s": parsed["parse_elapsed_s"],
            "total_s": elapsed,
        },
        "diagnostics": {
            **{
                key: value
                for key, value in parsed["diagnostics"].items()
                if key not in {"warnings", "errors"}
            },
            "query_count": state["query_count"],
            "materialized_part_saves": metrics.get("materialized_part_saves", 0),
        },
    }
