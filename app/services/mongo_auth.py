"""Mongo authentication posture checks (OPS-DBAUTH-01, Phase 5).

Mongo authentication is opt-in: `docker-compose.yml` passes
MONGO_INITDB_ROOT_USERNAME/PASSWORD through and leaves them empty by default,
so a stock deployment runs an unauthenticated database. That is deliberate —
enabling auth on an existing data volume requires creating users first, so it
cannot simply be switched on without breaking running instances.

What was missing is any signal that it is off. Nothing warned the operator, so
"unauthenticated" was both the default and invisible.

These helpers classify the configured URI so the application can warn on every
startup, and so `/api/ready` and the diagnostics surface can report it. Nothing
here changes connection behaviour.
"""

from __future__ import annotations

from urllib.parse import urlsplit


def _localhost_only(host: str) -> bool:
    """Is every host in this connection string loopback?

    An unauthenticated Mongo bound to loopback is a normal developer setup and
    not worth alarming about. One reachable over a network is a real exposure.
    """
    if not host:
        return False
    candidates = [item.strip() for item in host.split(",") if item.strip()]
    if not candidates:
        return False
    for candidate in candidates:
        # An IPv6 literal is bracketed, so its own colons must not be mistaken
        # for a port separator: "[::1]:27017" -> "::1".
        if candidate.startswith("["):
            name = candidate[1:].split("]", 1)[0]
        else:
            # Only a single trailing colon can be a port; anything else is a
            # bare IPv6 address written without brackets.
            name = candidate.rsplit(":", 1)[0] if candidate.count(":") == 1 else candidate
        name = name.strip("[]").lower()
        if name not in ("localhost", "127.0.0.1", "::1", "0:0:0:0:0:0:0:1"):
            return False
    return True


def describe_mongo_auth(uri: str) -> dict[str, object]:
    """Classify a Mongo URI's authentication posture.

    Returns a dict with:
      authenticated  credentials are present in the URI
      localhost_only every host is loopback
      risk           "ok" | "local-only" | "unauthenticated"
      message        operator-facing explanation, or "" when fine

    Never includes the URI, the password or the host in `message`, because the
    result is surfaced to logs and to the unauthenticated readiness endpoint.
    """
    raw = (uri or "").strip()
    if not raw:
        return {
            "authenticated": False,
            "localhost_only": False,
            "risk": "unauthenticated",
            "message": "No MONGO_URI is configured.",
        }

    try:
        parsed = urlsplit(raw)
        username = parsed.username or ""
        host = parsed.hostname or ""
        # urlsplit only exposes the first host of a seed list; use netloc for
        # the multi-host case so a replica set is classified correctly.
        netloc_hosts = parsed.netloc.split("@")[-1]
    except Exception:
        # An unparseable URI is not this function's problem to raise on; report
        # it as unknown rather than crashing startup.
        return {
            "authenticated": False,
            "localhost_only": False,
            "risk": "unauthenticated",
            "message": "MONGO_URI could not be parsed to check authentication.",
        }

    authenticated = bool(username)
    localhost_only = _localhost_only(netloc_hosts or host)

    if authenticated:
        return {
            "authenticated": True,
            "localhost_only": localhost_only,
            "risk": "ok",
            "message": "",
        }

    if localhost_only:
        return {
            "authenticated": False,
            "localhost_only": True,
            "risk": "local-only",
            "message": (
                "MongoDB has no authentication configured. The connection is "
                "loopback-only, so this is acceptable for local development "
                "but must not be used for a networked deployment."
            ),
        }

    return {
        "authenticated": False,
        "localhost_only": False,
        "risk": "unauthenticated",
        "message": (
            "MongoDB has NO AUTHENTICATION and is reachable over the network. "
            "Anyone who can reach the database port has full read/write access "
            "to all TinyMRP data. Set MONGO_ROOT_USER and MONGO_ROOT_PASSWORD "
            "and point MONGO_URI at "
            "mongodb://<user>:<pass>@<host>:27017/<db>?authSource=admin. "
            "For an existing data volume, create the users BEFORE enabling "
            "auth - see docs/UPDATING_PRODUCTION.md."
        ),
    }
