"""Run the Playwright help-screenshot capture against a seeded dev server.

Credentials are deliberately supplied through HELP_ADMIN_* and HELP_CUSTOMER_*
environment variables. The browser implementation lives with the frontend
tooling that already owns Playwright and Chromium.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SCRIPT = REPO_ROOT / "frontend" / "tools" / "capture-help-shots.mjs"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:5000")
    # Retained so an older documented invocation does not fail. Playwright now
    # waits for the actual page state instead of applying one delay everywhere.
    parser.add_argument("--settle", help=argparse.SUPPRESS)
    args = parser.parse_args()

    environment = os.environ.copy()
    environment["HELP_BASE_URL"] = args.base.rstrip("/")
    subprocess.run(
        ["node", str(CAPTURE_SCRIPT)],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
    )


if __name__ == "__main__":
    main()
