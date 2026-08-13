"""How the BROWSER reaches this instance, and what that implies.

Two hardening measures assume TLS and silently break a deployment that does
not have it:

* ``Secure`` session cookies. A browser refuses to store, and refuses to send,
  a ``Secure`` cookie over plain HTTP. Login then appears to succeed and
  immediately bounces back to the login form, because neither the CSRF token
  nor the session survives the redirect.
* The CSP ``upgrade-insecure-requests`` directive. It rewrites every
  subresource request to ``https://``, so on a plain-HTTP origin the browser
  asks for TLS on a port that speaks HTTP and every script, stylesheet and
  image fails to load.

Both were previously gated behind the old ``TINYMRP_SECURITY_MODE=strict``
opt-in. Removing compat mode made the strict branch unconditional, which is
correct for the HTTPS deployments it was written for and fatal for a
plain-HTTP LAN one.

Neither failure shows up on ``http://localhost``: the web platform classifies
loopback as a *potentially trustworthy* origin, so ``Secure`` cookies are
stored anyway and ``upgrade-insecure-requests`` skips it. A LAN IP gets no such
carve-out, which is exactly why developer machines kept working while a LAN
deployment did not.

So the question this module answers is not "how paranoid should we be" but a
factual one: **does the browser reach this instance over TLS?** Everything else
follows from the answer, and the answer comes from the address operators
already have to declare.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

# Loopback is a potentially trustworthy origin, so plain HTTP there carries no
# network exposure and deserves no warning.
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})

# Checked in order. TINYMRP_URL is the documented setting; the others let an
# instance created before it existed pick up the right posture on upgrade
# without its configuration being rewritten first.
_URL_SOURCES = ("TINYMRP_URL", "INSTANCE_URL")


class TransportConfigurationError(RuntimeError):
    """The declared public address cannot be interpreted."""


@dataclass(frozen=True)
class TransportPosture:
    """The resolved answer plus enough provenance to explain it in a log line."""

    public_url: str
    origin: str
    host: str
    browser_tls: bool
    source: str
    detail: str
    warning: str | None = None


def _clean(value: str | None) -> str:
    return str(value or "").strip()


def _parse_bool(name: str, raw: str) -> bool | None:
    lowered = raw.casefold()
    if lowered in ("", "auto"):
        return None
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    raise TransportConfigurationError(
        f"{name} must be true, false, or auto (got {raw!r})."
    )


def normalize_public_url(value: str, *, source: str, strict: bool) -> tuple[str, str, str]:
    """Return ``(url, origin, host)`` for a declared address.

    ``strict`` distinguishes the setting an operator typed on purpose from a
    value inherited from older configuration. A malformed ``TINYMRP_URL`` is an
    error worth stopping for; a malformed legacy value is ignored, because
    refusing to boot over it would break instances that run fine today.
    """

    raw = _clean(value)
    if not raw:
        return "", "", ""

    def _reject(reason: str) -> tuple[str, str, str]:
        if strict:
            raise TransportConfigurationError(
                f"{source}={raw!r} {reason} Use a full address including the "
                "scheme, for example http://192.168.1.50:5000 or "
                "https://tinymrp.example.com."
            )
        return "", "", ""

    if "://" not in raw:
        return _reject("has no scheme.")

    parsed = urlsplit(raw.rstrip("/"))
    if parsed.scheme not in ("http", "https"):
        return _reject(f"uses an unsupported scheme {parsed.scheme!r}.")
    if not parsed.hostname:
        return _reject("has no host.")

    # netloc, not hostname: the port is part of the origin, and dropping it
    # would produce an origin that never matches what the browser sends.
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return origin + parsed.path.rstrip("/"), origin, parsed.hostname.casefold()


def is_loopback_host(host: str) -> bool:
    return _clean(host).casefold() in LOOPBACK_HOSTS


def _first_allowed_origin(environ: Mapping[str, str]) -> str:
    """The first entry of the CORS allowlist, used as a last-resort hint.

    Every installer has written this for years, always as the instance's own
    address, so it identifies the scheme for an instance upgraded from before
    TINYMRP_URL existed.
    """

    raw = _clean(environ.get("TINYMRP_ALLOWED_ORIGINS"))
    for entry in raw.split(","):
        candidate = _clean(entry)
        if candidate and candidate not in ("*", "all"):
            return candidate
    return ""


def resolve_transport_posture(
    environ: Mapping[str, str] | None = None,
) -> TransportPosture:
    """Decide whether browsers reach this instance over TLS."""

    environ = os.environ if environ is None else environ

    public_url = origin = host = ""
    url_source = ""
    for name in _URL_SOURCES:
        public_url, origin, host = normalize_public_url(
            environ.get(name, ""), source=name, strict=(name == "TINYMRP_URL")
        )
        if origin:
            url_source = name
            break
    if not origin:
        public_url, origin, host = normalize_public_url(
            _first_allowed_origin(environ),
            source="TINYMRP_ALLOWED_ORIGINS",
            strict=False,
        )
        if origin:
            url_source = "TINYMRP_ALLOWED_ORIGINS"

    override = _parse_bool(
        "TINYMRP_BROWSER_TLS", _clean(environ.get("TINYMRP_BROWSER_TLS"))
    )
    if override is not None:
        browser_tls = override
        source = "TINYMRP_BROWSER_TLS"
        detail = f"TINYMRP_BROWSER_TLS={'true' if override else 'false'}"
    elif origin:
        browser_tls = origin.startswith("https://")
        source = url_source
        detail = f"{url_source}={origin}"
    else:
        # Nothing declared. Assume TLS: that is what every deployment before
        # this setting existed got, and the failure mode of guessing wrong in
        # this direction is a visible broken login rather than a silent
        # downgrade of a public instance.
        browser_tls = True
        source = "default"
        detail = "no public address configured; assuming HTTPS"

    warning = None
    if not browser_tls and origin and not is_loopback_host(host):
        warning = (
            f"TinyMRP is serving {origin} without TLS, so session cookies and "
            "passwords cross the network in clear text. This is supported for "
            "trusted private networks only. Put the instance behind HTTPS "
            "before exposing it beyond a LAN."
        )
    elif not browser_tls and not origin:
        warning = (
            "TINYMRP_BROWSER_TLS=false was set without a public address. "
            "Set TINYMRP_URL so logs, CORS defaults and links agree on how "
            "users reach this instance."
        )

    return TransportPosture(
        public_url=public_url,
        origin=origin,
        host=host,
        browser_tls=browser_tls,
        source=source,
        detail=detail,
        warning=warning,
    )


def resolve_trusted_proxy_hops(environ: Mapping[str, str] | None = None) -> int:
    """How many reverse proxies in front of the app may be believed.

    ``X-Forwarded-For`` and ``X-Forwarded-Proto`` are attacker-controlled unless
    a proxy you own overwrites them. The default of 1 matches every guided
    deployment, which puts Caddy or Nginx in front. Set 0 when the application
    port is reachable directly - otherwise a client can forge its own source
    address and step around IP-keyed rate limits.
    """

    environ = os.environ if environ is None else environ
    raw = _clean(environ.get("TINYMRP_TRUSTED_PROXY_HOPS"))
    if not raw:
        return 1
    try:
        hops = int(raw)
    except ValueError as exc:
        raise TransportConfigurationError(
            "TINYMRP_TRUSTED_PROXY_HOPS must be a non-negative integer."
        ) from exc
    if hops < 0:
        raise TransportConfigurationError(
            "TINYMRP_TRUSTED_PROXY_HOPS must be a non-negative integer."
        )
    return hops
