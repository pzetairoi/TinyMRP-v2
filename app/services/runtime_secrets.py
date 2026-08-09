from __future__ import annotations

import json
import logging
import os
import secrets as _secrets
import time
from typing import Tuple

logger = logging.getLogger(__name__)


_DEFAULT_VALUES = {
    "change-me",
    "changeme",
    "change-me-too",
    "please-change",
    "please-change-too",
    "default",
    "secret",
}


def _normalize_env(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    raw = str(raw).strip()
    if not raw:
        return None
    return raw


def _is_default(value: str | None) -> bool:
    if not value:
        return True
    return value.strip().lower() in _DEFAULT_VALUES


def _is_weak(value: str | None) -> bool:
    if not value:
        return True
    return len(value.strip()) < 16


def _runtime_path(app) -> str:
    override = os.getenv("TINYMRP_RUNTIME_SECRETS_PATH")
    if override and override.strip():
        return os.path.abspath(override.strip())
    base = getattr(app, "instance_path", "") or ""
    if not base:
        base = os.path.abspath(os.path.join(os.getcwd(), "instance"))
    return os.path.join(base, "runtime_secrets.json")


def _load_runtime_file(path: str) -> dict:
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh) or {}
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_runtime_file(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        # This file holds secrets. A failed chmod means it may be readable by
        # every account on the host, and that must not pass unnoticed.
        logger.warning("could not restrict permissions on %s", tmp, exc_info=True)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        logger.warning("could not restrict permissions on %s", path, exc_info=True)


def _acquire_lock(path: str, timeout: float = 5.0) -> str | None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    lock_path = f"{path}.lock"
    start = time.time()
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.close(fd)
            return lock_path
        except FileExistsError:
            if time.time() - start >= timeout:
                return None
            time.sleep(0.05)


def _release_lock(lock_path: str | None) -> None:
    if not lock_path:
        return
    try:
        os.remove(lock_path)
    except Exception:
        pass


def resolve_runtime_secrets(app, mode: str = "strict") -> Tuple[str, str]:
    """Return (secret_key, password_salt), or refuse to start.

    There used to be a second path that generated secrets and persisted them to
    a file when none were supplied. It existed for compat mode, which is gone.
    An application that invents its own signing key cannot tell a forged
    session from a real one after a restart, so this now fails loudly instead.

    `mode` is accepted and ignored so existing callers keep working.
    """
    env_secret = _normalize_env("SECRET_KEY")
    env_salt = _normalize_env("SECURITY_PASSWORD_SALT")

    if _is_default(env_secret) or _is_weak(env_secret):
        raise RuntimeError("SECRET_KEY must be set to a strong value.")
    if _is_default(env_salt) or _is_weak(env_salt):
        raise RuntimeError("SECURITY_PASSWORD_SALT must be set to a strong value.")
    return env_secret or "", env_salt or ""
