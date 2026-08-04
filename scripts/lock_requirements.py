"""Regenerate requirements.lock from requirements.txt (SUPPLY-LOCK-01).

    python scripts/lock_requirements.py

Writes a fully resolved, hash-pinned lock file that `pip install
--require-hashes` accepts. Run it whenever requirements.txt changes; CI fails
if the two drift.

Why the whole tree and not just the direct pins: pip refuses --require-hashes
unless EVERY package in the resolution is pinned and hashed. A lock containing
only the direct requirements appears to work in an environment where the
transitive packages already exist, then fails on a clean machine - which is
exactly where supply-chain integrity matters. The resolution is therefore taken
from pip's own resolver report rather than parsed by hand.

All published sha256 artifacts for each version are listed, so a Linux
container and a Windows dev box both validate against the same file.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = REPO_ROOT / "requirements.txt"
LOCKFILE = REPO_ROOT / "requirements.lock"

HEADER = """\
# TinyMRP v2 - hash-locked dependency set (SUPPLY-LOCK-01).
#
# GENERATED FILE - do not edit by hand. Regenerate with:
#     python scripts/lock_requirements.py
#
# Install with:
#     pip install --require-hashes -r requirements.lock
#
# Contains the FULLY RESOLVED tree - direct requirements AND their transitive
# dependencies. pip refuses --require-hashes unless every package in the
# resolution is pinned and hashed, so a partial lock silently fails on a clean
# environment even though it appears to work where packages already exist.
#
# All published artifacts for each version are listed so any platform's wheel
# validates; an artifact whose hash is absent is refused.
"""


def resolve_tree() -> list[dict]:
    """Ask pip to resolve requirements.txt and report what it would install."""
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        subprocess.run(
            [
                sys.executable, "-m", "pip", "install",
                "--dry-run", "--quiet",
                "--report", str(report),
                "-r", str(REQUIREMENTS),
            ],
            check=True,
        )
        data = json.loads(report.read_text(encoding="utf-8"))
    return data.get("install", [])


def artifact_hashes(name: str, version: str) -> list[str]:
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    with urllib.request.urlopen(url, timeout=30) as handle:
        payload = json.load(handle)
    return sorted({item["digests"]["sha256"] for item in payload.get("urls") or []})


def main() -> int:
    entries = resolve_tree()
    if not entries:
        print("resolver returned nothing; aborting", file=sys.stderr)
        return 1

    rows = []
    for entry in entries:
        metadata = entry["metadata"]
        name, version = metadata["name"], metadata["version"]
        hashes = artifact_hashes(name, version)
        if not hashes:
            # Fall back to the hash pip itself resolved, so a package missing
            # from the JSON API still locks rather than being skipped.
            archive = entry.get("download_info", {}).get("archive_info", {})
            hashes = sorted(set((archive.get("hashes") or {}).values()))
        if not hashes:
            print(f"no artifacts found for {name}=={version}", file=sys.stderr)
            return 1
        rows.append((name, version, hashes, bool(entry.get("requested"))))

    rows.sort(key=lambda row: row[0].lower())
    direct = sum(1 for row in rows if row[3])

    lines = [HEADER.rstrip("\n"), "#",
             f"# {len(rows)} packages ({direct} direct, {len(rows) - direct} transitive).",
             ""]
    for name, version, hashes, _ in rows:
        lines.append(f"{name}=={version} \\")
        for index, digest in enumerate(hashes):
            suffix = " \\" if index < len(hashes) - 1 else ""
            lines.append(f"    --hash=sha256:{digest}{suffix}")

    LOCKFILE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {LOCKFILE.name}: {len(rows)} packages ({direct} direct)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
