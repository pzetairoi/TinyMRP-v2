#!/usr/bin/env python3
"""HTTP smoke checks for a freshly bootstrapped Compose deployment."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser


class _CsrfParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.token = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "input":
            return
        values = dict(attrs)
        if values.get("name") == "csrf_token":
            self.token = values.get("value") or ""


def _json_response(response) -> dict:
    content_type = response.headers.get_content_type()
    if content_type != "application/json":
        raise RuntimeError(f"Expected JSON, received {content_type!r} from {response.url}")
    return json.loads(response.read().decode("utf-8"))


def _open(opener, request, *, timeout: float):
    try:
        return opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read(500).decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {exc.url}: {body}") from exc


def run_smoke(base_url: str, email: str, password: str, token: str, timeout: float) -> None:
    base_url = base_url.rstrip("/")
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    health = _json_response(_open(opener, f"{base_url}/api/health", timeout=timeout))
    if health.get("ok") is not True or health.get("service") != "tinymrp":
        raise RuntimeError(f"Health response is not ready: {health!r}")

    login_response = _open(opener, f"{base_url}/login", timeout=timeout)
    parser = _CsrfParser()
    parser.feed(login_response.read().decode("utf-8"))
    if not parser.token:
        raise RuntimeError("Login form did not contain a CSRF token.")

    body = urllib.parse.urlencode(
        {
            "email": email,
            "password": password,
            "csrf_token": parser.token,
            "remember": "y",
            "submit": "Login",
        }
    ).encode("utf-8")
    login_request = urllib.request.Request(
        f"{base_url}/login",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{base_url}/login",
        },
    )
    _open(opener, login_request, timeout=timeout).read()

    account_response = _open(opener, f"{base_url}/app", timeout=timeout)
    account_html = account_response.read().decode("utf-8", errors="replace")
    if account_response.geturl().rstrip("/").endswith("/login") or email not in account_html:
        raise RuntimeError("Web login did not establish an authenticated administrator session.")

    auth_request = urllib.request.Request(
        f"{base_url}/api/auth/check",
        headers={"Authorization": f"Bearer {token}"},
    )
    auth = _json_response(_open(opener, auth_request, timeout=timeout))
    if auth.get("ok") is not True:
        raise RuntimeError(f"Protected API rejected the token: {auth!r}")
    api_user = auth.get("user") or {}
    if api_user.get("email") != email or "administrator" not in api_user.get("roles", []):
        raise RuntimeError(f"Protected API returned the wrong principal: {api_user!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password-env", default="TINYMRP_SMOKE_PASSWORD")
    parser.add_argument("--token-env", default="TINYMRP_SMOKE_TOKEN")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    password = os.environ.get(args.password_env) or ""
    token = os.environ.get(args.token_env) or ""
    if not password or not token:
        parser.error(
            f"{args.password_env} and {args.token_env} must contain the ephemeral smoke credentials"
        )

    run_smoke(args.base_url, args.email, password, token, args.timeout)
    print("Fresh Compose HTTP smoke passed: health, login, and protected API.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
