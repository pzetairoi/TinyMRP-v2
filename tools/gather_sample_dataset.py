#!/usr/bin/env python3
"""Gather only CV03 BOM-family deliverables and regenerate its manifest."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = REPO_ROOT / "sample_data" / "cv03_tr_a01_rev_a"
MANAGED_ROOT = DATASET_ROOT / "managed"
BOM_NAME = "CV03-TR-A01_REV_A_2026_07_11_16_41_58.zip"
GROUPS = {"3mf", "bom", "datasheet", "dxf", "edr", "pdf", "ply", "png", "step", "stl", "thumbs"}


def _bom_pairs(archive: Path) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    with zipfile.ZipFile(archive) as bundle:
        flat_name = next(name for name in bundle.namelist() if name.casefold().endswith("_flatbom.txt"))
        tree_name = next(name for name in bundle.namelist() if name.casefold().endswith("_treebom.txt"))
        for line in bundle.read(flat_name).decode("utf-8-sig").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except (TypeError, ValueError):
                row = ast.literal_eval(line)
            lowered = {str(key).strip().casefold(): value for key, value in row.items()}
            part_number = str(
                lowered.get("partnumber")
                or lowered.get("part_number")
                or lowered.get("pn")
                or ""
            ).split("^", 1)[0].strip()
            revision = str(lowered.get("revision") or lowered.get("rev") or "").strip()
            if part_number:
                pairs.add((part_number.casefold(), revision.casefold()))
        for line in bundle.read(tree_name).decode("utf-8-sig").splitlines()[1:]:
            columns = line.split("\t")
            if len(columns) >= 3 and columns[1].strip():
                pairs.add(
                    (
                        columns[1].strip().split("^", 1)[0].casefold(),
                        columns[2].strip().casefold(),
                    )
                )
    return pairs


def _identity(path: Path, pairs: set[tuple[str, str]]) -> tuple[str, str] | None:
    base = path.stem
    if base.casefold().endswith(".thumbnail"):
        base = base[:-10]
    if base.casefold().endswith("_dwg"):
        base = base[:-4]
    marker = base.upper().rfind("_REV_")
    if marker > 0:
        return base[:marker].strip().casefold(), base[marker + 5 :].strip().casefold()
    folded = base.casefold()
    return next((pair for pair in pairs if not pair[1] and pair[0] == folded), None)


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    source_root = args.source.resolve(strict=True)
    bom_archive = MANAGED_ROOT / "bom" / BOM_NAME
    pairs = _bom_pairs(bom_archive)
    matched: list[tuple[Path, Path]] = []
    for source in source_root.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(source_root)
        group = relative.parts[0].casefold() if relative.parts else ""
        if group not in GROUPS:
            continue
        include = _identity(source, pairs) in pairs
        if group == "bom":
            include = any(
                revision
                and source.name.casefold().startswith(f"{part_number}_rev_{revision}_")
                for part_number, revision in pairs
            )
        if include:
            matched.append((source, relative))

    unavailable: list[dict[str, str]] = []
    available: list[tuple[Path, Path]] = []
    for source, relative in matched:
        target = MANAGED_ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if target.exists() and not args.overwrite:
                if target.stat().st_size != source.stat().st_size or _digest(target) != _digest(source):
                    raise RuntimeError(f"Fixture differs from source: {relative}")
            else:
                shutil.copy2(source, target)
            available.append((source, relative))
        except OSError as exc:
            unavailable.append({"path": relative.as_posix(), "error": str(exc)})

    entries = []
    for _source, relative in sorted(available, key=lambda item: item[1].as_posix().casefold()):
        fixture = MANAGED_ROOT / relative
        entries.append(
            {
                "path": relative.as_posix(),
                "bytes": fixture.stat().st_size,
                "sha256": _digest(fixture),
            }
        )
    manifest = {
        "dataset_id": "cv03-tr-a01-rev-a",
        "part_number": "CV03-TR-A01",
        "revision": "A",
        "description": "CELLV03 Trailer",
        "approver": "TinyManager",
        "part_revision_count": len(pairs),
        "bom_source": f"managed/bom/{BOM_NAME}",
        "managed_files": entries,
        "unavailable_files": unavailable,
    }
    (DATASET_ROOT / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    groups = Counter(entry["path"].split("/", 1)[0] for entry in entries)
    print(
        json.dumps(
            {
                "part_revisions": len(pairs),
                "files": len(entries),
                "bytes": sum(entry["bytes"] for entry in entries),
                "groups": dict(sorted(groups.items())),
                "unavailable": unavailable,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
