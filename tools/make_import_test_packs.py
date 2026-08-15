#!/usr/bin/env python3
"""Write the import-policy exercise packs to disk as loose files.

The packs themselves are built by ``app.services.import_practice_packs`` (see
that module's docstring for what they are and why they live under
``app/services`` rather than here). This script is the CLI entry point for
anyone who wants them as files on disk instead of downloading the bundle ZIP
from the Import help page.

Usage::

    python tools/make_import_test_packs.py                # testfiles/import_scenarios
    python tools/make_import_test_packs.py --out C:/tmp/packs --prefix DEMO-

Then upload the numbered ZIPs in order on the Import page. The generated
README.md in the output folder repeats the story and the expected outcome of
each step; the full explanation is in the app help, chapter "Import: what each
choice does".
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.import_practice_packs import (  # noqa: E402
    Builder,
    _index_payload,
    _out_of_band_files,
    _readme,
    build_packs,
)

DEFAULT_OUT = REPO_ROOT / "testfiles" / "import_scenarios"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--prefix",
        default="IMPTEST-",
        help="Part-number prefix that keeps the exercise away from real data.",
    )
    parser.add_argument("--clean", action="store_true", help="Empty the output folder first.")
    args = parser.parse_args()

    builder = Builder(args.prefix)
    out_dir: Path = args.out
    if args.clean and out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "out_of_band").mkdir(parents=True, exist_ok=True)

    packs = build_packs(builder)
    written = []
    for pack in packs:
        path = builder.write(pack, out_dir)
        written.append({"pack": path.name, "bytes": path.stat().st_size, "title": pack.title})

    for name, payload in _out_of_band_files(builder).items():
        target = out_dir / "out_of_band" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    (out_dir / "README.md").write_text(_readme(builder, packs), encoding="utf-8")
    (out_dir / "index.json").write_text(
        json.dumps(_index_payload(builder, packs), indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"out": str(out_dir), "packs": written}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
