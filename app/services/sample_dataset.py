"""Owner-approved engineering sample fixture and safe installers."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from app.models.artifact import PartFile
from app.models.bom import BOMLink
from app.models.part import Part
from app.services.canonical_fields import (
    APPROVED_BY_ATTR_ALIASES,
    APPROVED_DATE_ATTR_ALIASES,
    APPROVED_STATUS_ATTR_ALIASES,
    canonical_attr_key,
)
from app.services.timezone_utils import utc_now
from app.services.upload_pack import parse_import_package


DATASET_ID = "cv03-tr-a01-rev-a"
PART_NUMBER = "CV03-TR-A01"
REVISION = "A"
APPROVER = "TinyManager"
DATASET_ROOT = Path(__file__).resolve().parents[2] / "sample_data" / "cv03_tr_a01_rev_a"
MANAGED_ROOT = DATASET_ROOT / "managed"
MANIFEST_PATH = DATASET_ROOT / "manifest.json"


def load_sample_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def verify_sample_fixture() -> dict[str, int]:
    manifest = load_sample_manifest()
    checked = 0
    total_bytes = 0
    for entry in manifest["managed_files"]:
        source = MANAGED_ROOT / entry["path"]
        if not source.is_file():
            raise FileNotFoundError(f"Sample fixture is missing {entry['path']}")
        size = source.stat().st_size
        if size != int(entry["bytes"]):
            raise ValueError(f"Sample fixture size mismatch: {entry['path']}")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            raise ValueError(f"Sample fixture checksum mismatch: {entry['path']}")
        checked += 1
        total_bytes += size
    return {"files": checked, "bytes": total_bytes}


def install_sample_deliverables(
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> dict[str, int]:
    """Copy the managed fixture tree without replacing files by default."""

    target_root = Path(destination).expanduser()
    if not str(target_root).strip():
        raise ValueError("A non-empty deliverables destination is required.")
    verify_sample_fixture()
    copied = skipped = 0
    copied_bytes = 0
    for entry in load_sample_manifest()["managed_files"]:
        source = MANAGED_ROOT / entry["path"]
        target = target_root / entry["path"]
        if target.exists() and not overwrite:
            skipped += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
        copied_bytes += source.stat().st_size
    return {
        "copied": copied,
        "skipped": skipped,
        "bytes": copied_bytes,
    }


def _parse_sample_bom() -> dict[str, Any]:
    manifest = load_sample_manifest()
    archive = DATASET_ROOT / manifest["bom_source"]
    return parse_import_package(
        archive.read_bytes(),
        archive.name,
        {"allow_extra": False},
    )


def _fixture_file_groups(
    pairs: set[tuple[str, str]],
) -> dict[tuple[str, str], set[str]]:
    folded = {(pn.casefold(), rev.casefold()): (pn, rev) for pn, rev in pairs}
    coverage: dict[tuple[str, str], set[str]] = {pair: set() for pair in pairs}
    for entry in load_sample_manifest()["managed_files"]:
        path = Path(entry["path"])
        group = path.parts[0].casefold() if path.parts else ""
        if group in {"bom", "thumbs"}:
            continue
        base = path.stem
        if base.casefold().endswith(".thumbnail"):
            base = base[:-10]
        if base.casefold().endswith("_dwg"):
            base = base[:-4]
        marker = base.upper().rfind("_REV_")
        if marker > 0:
            identity = (
                base[:marker].strip().casefold(),
                base[marker + 5 :].strip().casefold(),
            )
        else:
            identity = (base.casefold(), "")
        pair = folded.get(identity)
        if pair:
            coverage[pair].add(group)
    return coverage


def _fixture_part_files(
    pairs: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    folded = {(pn.casefold(), rev.casefold()): (pn, rev) for pn, rev in pairs}
    records: list[dict[str, Any]] = []
    for entry in load_sample_manifest()["managed_files"]:
        relative = Path(entry["path"])
        group = relative.parts[0].casefold() if relative.parts else ""
        if group in {"bom", "thumbs"} or relative.stem.casefold().endswith(".thumbnail"):
            continue
        base = relative.stem
        drawing = base.casefold().endswith("_dwg")
        if drawing:
            base = base[:-4]
        marker = base.upper().rfind("_REV_")
        identity = (
            (base[:marker].strip().casefold(), base[marker + 5 :].strip().casefold())
            if marker > 0
            else (base.casefold(), "")
        )
        pair = folded.get(identity)
        if not pair:
            continue
        records.append(
            {
                "part_number": pair[0],
                "revision": pair[1],
                "ext_group": group,
                "ext": relative.suffix.lstrip(".").casefold(),
                "is_dwg": drawing,
                "rel_path": relative.as_posix(),
                "path": str(MANAGED_ROOT / relative),
                "size": float(entry["bytes"]),
                "sha256": entry["sha256"],
                "source": "sample-fixture",
            }
        )
    return records


def ensure_sample_engineering_records() -> dict[str, int]:
    """Create missing sample records and release the exact BOM family."""

    parsed = _parse_sample_bom()
    created_parts = 0
    created_links = 0
    created_part_files = 0
    approvals_updated = 0
    coverage = _fixture_file_groups(set(parsed["parts"]))
    approval_aliases = {
        canonical_attr_key(alias)
        for alias in (
            *APPROVED_STATUS_ATTR_ALIASES,
            *APPROVED_BY_ATTR_ALIASES,
            *APPROVED_DATE_ATTR_ALIASES,
        )
    }
    for (part_number, revision), row in parsed["parts"].items():
        part = Part.objects(part_number=part_number, revision=revision).first()
        if part is None:
            part = Part(
                part_number=part_number,
                revision=revision,
                description=row.get("description") or "",
                category=row.get("category") or "",
                uom=row.get("uom") or "EA",
                attrs=dict(row.get("attrs") or {}),
            )
            created_parts += 1
        part.file_groups = sorted(coverage.get((part_number, revision), set()))
        attrs = {
            key: value
            for key, value in dict(part.attrs or {}).items()
            if canonical_attr_key(key) not in approval_aliases
        }
        attrs.update(
            {
                "approved": True,
                "approved_by": APPROVER,
                "approved_date": utc_now().date().isoformat(),
            }
        )
        before = dict(part.canonical or {})
        part.attrs = attrs
        part.save()
        after = dict(part.canonical or {})
        if (
            not before.get("approved")
            or before.get("approved_by") != APPROVER
            or before.get("approved_date") != after.get("approved_date")
        ):
            approvals_updated += 1

    for parent_pn, parent_rev, child_pn, child_rev, qty, occurrences in parsed["links"]:
        exists = BOMLink.objects(
            parent_pn=parent_pn,
            parent_rev=parent_rev,
            child_pn=child_pn,
            child_rev=child_rev,
        ).first()
        if exists:
            continue
        BOMLink(
            parent_pn=parent_pn,
            parent_rev=parent_rev,
            child_pn=child_pn,
            child_rev=child_rev,
            qty=qty,
            occurrences=list(occurrences or []),
        ).save()
        created_links += 1

    existing_file_keys = {
        (
            str(row.part_number or "").casefold(),
            str(row.revision or "").casefold(),
            str(row.ext_group or "").casefold(),
            str(row.ext or "").casefold(),
            bool(row.is_dwg),
        )
        for row in PartFile.objects(
            part_number__in=sorted({part_number for part_number, _revision in parsed["parts"]})
        ).only("part_number", "revision", "ext_group", "ext", "is_dwg")
    }
    new_file_docs = []
    for record in _fixture_part_files(set(parsed["parts"])):
        key = (
            record["part_number"].casefold(),
            record["revision"].casefold(),
            record["ext_group"].casefold(),
            record["ext"].casefold(),
            bool(record["is_dwg"]),
        )
        if key in existing_file_keys:
            continue
        existing_file_keys.add(key)
        new_file_docs.append(PartFile(**record))
    if new_file_docs:
        PartFile.objects.insert(new_file_docs, load_bulk=False)
        created_part_files = len(new_file_docs)

    from app.services.part_materialized import sync_materialized_fields_for_pairs

    sync_materialized_fields_for_pairs(set(parsed["parts"]))

    return {
        "parts": created_parts,
        "bom_links": created_links,
        "approvals_updated": approvals_updated,
        "part_files": created_part_files,
        "part_files_total": len(_fixture_part_files(set(parsed["parts"]))),
        "parts_total": len(parsed["parts"]),
        "bom_links_total": len(parsed["links"]),
    }
