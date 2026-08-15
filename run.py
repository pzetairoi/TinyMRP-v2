"""TinyMRP entry point: ``python run.py``.

Everything is read from the environment (or from the file named by ``ENV_FILE``,
which ``create_app`` loads before anything here runs), so this file never needs
a local edit. That matters on locked-down hosts where ``python.exe run.py`` is
the one command that has been approved: editing run.py to change a port used to
be the only option, and every such edit then collided with the next ``git pull``.

    ENV_FILE=.env.dev python run.py
    set ENV_FILE=C:\\TinyMRP\\config\\.env.lan && python run.py

What it decides, and how to override each decision:

    TINYMRP_BIND_HOST    interface to listen on. Defaults to 0.0.0.0 when
                         TINYMRP_URL names a non-loopback host - otherwise a
                         server other people are meant to reach would come up
                         listening only to itself - and 127.0.0.1 otherwise.
    TINYMRP_BIND_PORT    port to listen on. Defaults to the port in
                         TINYMRP_URL, then 5000, so the address is declared
                         once and the listener follows it.
    TINYMRP_SERVER       "waitress" (default when installed) or "flask".
    TINYMRP_DEV          "1" enables the Flask debugger and reloader.

The debugger is off unless asked for, and refuses to bind a non-loopback
interface: Werkzeug's interactive traceback console executes arbitrary Python
in the server process, so a debug server reachable from the network is remote
code execution wearing a friendly error page.
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urlsplit

from app import create_app

app = create_app()


def _flag(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _public_host() -> str:
    origin = str(app.config.get("TINYMRP_PUBLIC_ORIGIN") or "").strip()
    return urlsplit(origin).hostname or "" if origin else ""


def _public_port() -> int | None:
    origin = str(app.config.get("TINYMRP_PUBLIC_ORIGIN") or "").strip()
    if not origin:
        return None
    parsed = urlsplit(origin)
    if parsed.port:
        return parsed.port
    return 443 if parsed.scheme == "https" else 80


def _resolve_bind() -> tuple[str, int]:
    from app.services.transport_posture import is_loopback_host

    host = str(os.getenv("TINYMRP_BIND_HOST") or "").strip()
    if not host:
        public_host = _public_host()
        host = "127.0.0.1" if (not public_host or is_loopback_host(public_host)) else "0.0.0.0"

    raw_port = str(os.getenv("TINYMRP_BIND_PORT") or "").strip()
    if raw_port:
        try:
            port = int(raw_port)
        except ValueError:
            raise SystemExit(f"TINYMRP_BIND_PORT must be a number (got {raw_port!r}).")
    else:
        port = _public_port() or 5000
    if not 1 <= port <= 65535:
        raise SystemExit(f"TINYMRP_BIND_PORT must be between 1 and 65535 (got {port}).")
    return host, port


def _resolve_server(debug: bool) -> str:
    choice = str(os.getenv("TINYMRP_SERVER") or "").strip().lower()
    if choice in ("flask", "werkzeug", "dev"):
        return "flask"
    if choice == "waitress":
        return "waitress"
    if choice:
        raise SystemExit(f"TINYMRP_SERVER must be 'waitress' or 'flask' (got {choice!r}).")
    if debug:
        # The reloader and the interactive debugger are Werkzeug features.
        return "flask"
    try:
        import waitress  # noqa: F401
    except ImportError:
        return "flask"
    return "waitress"


def main() -> int:
    from app.services.transport_posture import is_loopback_host

    debug = _flag("TINYMRP_DEV") or _flag("FLASK_DEBUG")
    host, port = _resolve_bind()
    server = _resolve_server(debug)
    remote = host not in ("127.0.0.1", "::1", "localhost")

    if debug and remote and not _flag("TINYMRP_ALLOW_REMOTE_DEBUG"):
        print(
            "REFUSING TO START: the Flask debugger is enabled (TINYMRP_DEV=1) while\n"
            f"binding {host}, which other machines can reach. Werkzeug's traceback\n"
            "console runs arbitrary Python in this process, so that combination hands\n"
            "the server to anyone who can load a page that raises.\n\n"
            "Pick one:\n"
            "  - drop TINYMRP_DEV to serve normally (this is what a shared server wants)\n"
            "  - set TINYMRP_BIND_HOST=127.0.0.1 to debug locally\n"
            "  - set TINYMRP_ALLOW_REMOTE_DEBUG=1 if you accept the risk on an\n"
            "    isolated network",
            file=sys.stderr,
        )
        return 2

    public = app.config.get("TINYMRP_URL") or f"http://{host}:{port}"
    print(f"TinyMRP listening on {host}:{port} ({server}, debug={'on' if debug else 'off'})")
    print(f"Users should open: {public}")
    if not app.config.get("TINYMRP_PUBLIC_ORIGIN"):
        print(
            "WARNING: TINYMRP_URL is not set, so TinyMRP assumes HTTPS and marks session\n"
            "         cookies Secure. Over plain HTTP a browser discards those cookies and\n"
            "         login silently returns to the login page. Set TINYMRP_URL to the\n"
            f"         address users type, e.g. http://{host if remote else 'localhost'}:{port}",
            file=sys.stderr,
        )
    elif remote and not is_loopback_host(_public_host()) and _public_port() != port:
        print(
            f"WARNING: TINYMRP_URL points at port {_public_port()} but this process is\n"
            f"         listening on {port}. The origin includes the port, so logins will\n"
            "         fail until the two agree.",
            file=sys.stderr,
        )

    if server == "waitress":
        from waitress import serve

        serve(
            app,
            host=host,
            port=port,
            threads=int(os.getenv("TINYMRP_THREADS") or "8"),
            connection_limit=int(os.getenv("TINYMRP_CONNECTION_LIMIT") or "200"),
            channel_timeout=int(os.getenv("TINYMRP_CHANNEL_TIMEOUT") or "120"),
            ident="TinyMRP",
        )
    else:
        app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
