"""Capture help screenshots from a running server using the demo accounts.

    python tools/capture_help_shots.py --base http://localhost:5000

Images land in ``app/static/help/img`` and are referenced from the markdown in
``docs/help``. Only add a shot when it shows something the text cannot say as
clearly -- repeated views of the same screen make the help longer, not clearer.

Requires a server seeded with the permission-test users, plus Chrome or Edge.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from base64 import b64decode
from pathlib import Path

import requests
import websocket

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "app" / "static" / "help" / "img"
DEBUG_PORT = 9222

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]

ACCOUNTS = {
    "administrator": ("permtest.administrator@demo.com", "lMQhB_5OIg2C7n1vYSFZMALl"),
    "engineering": ("permtest.engineering@demo.com", "QyMA7WoCnYdRDNphLY-uV9DG"),
    "customer": ("permtest.customer@demo.com", "Ca4RcV8rVX1BCTzb1JMEjsR1"),
}

# One shot per idea, captured as the role that actually sees it.
SHOTS = [
    {"name": "inventory", "url": "/ui/parts", "role": "administrator", "height": 900},
    {"name": "import", "url": "/ui/upload-pack", "role": "administrator", "height": 950},
    {"name": "roles", "url": "/admin/roles/", "role": "administrator", "height": 850},
    {"name": "customer-portal", "url": "/ui/parts", "role": "customer", "height": 620},
]

_CSRF_RE = re.compile(r'name="csrf_token"[^>]*value="([^"]+)"')


def _find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    found = shutil.which("chrome") or shutil.which("chromium")
    if found:
        return found
    raise SystemExit("No Chrome or Edge binary found; cannot capture screenshots.")


def _session_cookie(base: str, email: str, password: str) -> tuple[str, str]:
    session = requests.Session()
    match = _CSRF_RE.search(session.get(f"{base}/login", timeout=20).text)
    payload = {"email": email, "password": password}
    if match:
        payload["csrf_token"] = match.group(1)
    session.post(f"{base}/login", data=payload, timeout=20)
    if session.get(f"{base}/api/parts_lazy", timeout=20).status_code != 200:
        raise SystemExit(f"Login failed for {email}.")
    cookie = next(iter(session.cookies))
    return cookie.name, cookie.value


class Browser:
    """Minimal Chrome DevTools Protocol client: cookie, navigate, screenshot."""

    def __init__(self, binary: str, width: int) -> None:
        self.profile = tempfile.mkdtemp(prefix="tm_shots_")
        self.process = subprocess.Popen(
            [
                binary,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--user-data-dir={self.profile}",
                f"--remote-debugging-port={DEBUG_PORT}",
                f"--window-size={width},900",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.socket = self._connect()
        self.message_id = 0

    def _connect(self):
        for _ in range(40):
            try:
                info = json.load(
                    urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/list")
                )
                pages = [t for t in info if t.get("type") == "page"]
                if pages:
                    # Chrome rejects the handshake when an Origin header is
                    # present; suppress_origin omits it.
                    return websocket.create_connection(
                        pages[0]["webSocketDebuggerUrl"],
                        timeout=60,
                        suppress_origin=True,
                    )
            except Exception:
                pass
            time.sleep(0.5)
        raise SystemExit("Could not attach to the browser.")

    def send(self, method: str, **params):
        self.message_id += 1
        self.socket.send(json.dumps({"id": self.message_id, "method": method, "params": params}))
        while True:
            message = json.loads(self.socket.recv())
            if message.get("id") == self.message_id:
                return message.get("result", {})

    def set_cookie(self, name: str, value: str, domain: str) -> None:
        self.send("Network.enable")
        self.send(
            "Network.setCookie", name=name, value=value, domain=domain, path="/", httpOnly=True
        )

    def shot(self, url: str, path: Path, width: int, height: int, settle: float) -> bool:
        self.send(
            "Emulation.setDeviceMetricsOverride",
            width=width,
            height=height,
            deviceScaleFactor=1,
            mobile=False,
        )
        self.send("Page.enable")
        self.send("Page.navigate", url=url)
        time.sleep(settle)
        result = self.send("Page.captureScreenshot", format="png")
        data = result.get("data")
        if not data:
            return False
        path.write_bytes(b64decode(data))
        return True

    def close(self) -> None:
        try:
            self.socket.close()
        finally:
            self.process.terminate()
            shutil.rmtree(self.profile, ignore_errors=True)


def capture(base: str, settle: float) -> list[str]:
    binary = _find_chrome()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    domain = base.split("//", 1)[-1].split(":")[0]
    width = 1440
    written: list[str] = []

    for role in sorted({shot["role"] for shot in SHOTS}):
        email, password = ACCOUNTS[role]
        name, value = _session_cookie(base, email, password)
        browser = Browser(binary, width)
        try:
            browser.send("Page.navigate", url=f"{base}/login")
            time.sleep(1.0)
            browser.set_cookie(name, value, domain)
            for shot in [s for s in SHOTS if s["role"] == role]:
                target = OUT_DIR / f"{shot['name']}.png"
                ok = browser.shot(
                    f"{base}{shot['url']}", target, width, shot["height"], settle
                )
                if ok:
                    written.append(str(target.relative_to(REPO_ROOT)))
                else:
                    print(f"  ! {shot['name']}: no image", file=sys.stderr)
        finally:
            browser.close()
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:5000")
    parser.add_argument("--settle", type=float, default=6.0, help="seconds to let a page load")
    args = parser.parse_args()
    for path in capture(args.base.rstrip("/"), args.settle):
        print(f"  wrote {path}")


if __name__ == "__main__":
    main()
