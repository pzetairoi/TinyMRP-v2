from __future__ import annotations

import json
import os
import secrets as _secrets
import time
from typing import Tuple


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
        with open(path, "r", encoding="utf-8") as fh:
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
        pass
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def _acquire_lock(path: str, timeout: float = 5.0) -> str | None:
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


def resolve_runtime_secrets(app, mode: str) -> Tuple[str, str]:
    env_secret = _normalize_env("SECRET_KEY")
    env_salt = _normalize_env("SECURITY_PASSWORD_SALT")

    if mode == "strict":
        if _is_default(env_secret) or _is_weak(env_secret):
            raise RuntimeError("SECRET_KEY must be set to a strong value in strict mode.")
        if _is_default(env_salt) or _is_weak(env_salt):
            raise RuntimeError("SECURITY_PASSWORD_SALT must be set to a strong value in strict mode.")
        return env_secret or "", env_salt or ""

    # compat mode: use env when valid, otherwise load/persist runtime secrets
    secret = env_secret if not _is_default(env_secret) else None
    salt = env_salt if not _is_default(env_salt) else None

    if secret and salt:
        return secret, salt

    path = _runtime_path(app)
    data = _load_runtime_file(path)

    if not env_secret or _is_default(env_secret) or not env_salt or _is_default(env_salt):
        print(f"Warning: secrets missing/weak; using runtime secrets file at {path}. Set SECRET_KEY and SECURITY_PASSWORD_SALT for production/strict mode.")

    if not secret:
        stored_secret = data.get("SECRET_KEY")
        if isinstance(stored_secret, str) and stored_secret.strip():
            secret = stored_secret.strip()
    if not salt:
        stored_salt = data.get("SECURITY_PASSWORD_SALT")
        if isinstance(stored_salt, str) and stored_salt.strip():
            salt = stored_salt.strip()

    generated = False
    if not secret:
        secret = _secrets.token_urlsafe(32)
        data["SECRET_KEY"] = secret
        generated = True
    if not salt:
        salt = _secrets.token_urlsafe(32)
        data["SECURITY_PASSWORD_SALT"] = salt
        generated = True

    if generated:
        lock = _acquire_lock(path)
        try:
            existing = _load_runtime_file(path)
            # Preserve any keys that may have been written by another worker.
            if existing:
                for k, v in existing.items():
                    data.setdefault(k, v)
            _write_runtime_file(path, data)
        finally:
            _release_lock(lock)

    return secret, salt
