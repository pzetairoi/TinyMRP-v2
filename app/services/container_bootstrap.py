"""Safe, idempotent database bootstrap for container startup."""

from __future__ import annotations

import json
import os
import secrets
import sys
from collections.abc import Mapping
from typing import Any

from email_validator import EmailNotValidError, validate_email
from flask_security import hash_password

from app.models.auth import Role, User
from app.services.password_policy import validate_admin_password
from app.services.standard_roles import reconcile_standard_roles
from app.services.timezone_utils import utc_now

ADMIN_ROLE_SLUG = "administrator"
HISTORICAL_EXAMPLE_PASSWORD = "ChangeMe123!"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"", "0", "false", "no", "off"})


class BootstrapConfigurationError(RuntimeError):
    """The requested first-user bootstrap cannot be performed safely."""


def _parse_seed_admin(environ: Mapping[str, str]) -> bool:
    raw_value = str(environ.get("TINYMRP_SEED_ADMIN") or "").strip().lower()
    if raw_value in _TRUE_VALUES:
        return True
    if raw_value in _FALSE_VALUES:
        return False
    raise BootstrapConfigurationError(
        "TINYMRP_SEED_ADMIN must be one of true/false, 1/0, yes/no, or on/off."
    )


def validate_first_admin_credentials(email: str, password: str) -> tuple[str, str]:
    """Normalize and validate deliberate first-administrator credentials."""

    email = str(email or "").strip()
    password = str(password or "")
    if not email:
        raise BootstrapConfigurationError(
            "Administrator email is required when seeding the first administrator."
        )
    if not password:
        raise BootstrapConfigurationError(
            "Administrator password is required when seeding the first administrator."
        )
    if password == HISTORICAL_EXAMPLE_PASSWORD:
        raise BootstrapConfigurationError(
            "The historical example administrator password is forbidden; provide a unique strong password."
        )

    try:
        email = validate_email(email, check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise BootstrapConfigurationError("Administrator email must be valid.") from exc

    password_errors = validate_admin_password(password, email=email)
    if password_errors:
        raise BootstrapConfigurationError(" ".join(password_errors))
    return email, password


def _admin_credentials(environ: Mapping[str, str]) -> tuple[str, str]:
    email = str(environ.get("TINYMRP_ADMIN_EMAIL") or environ.get("DEFAULT_ADMIN_EMAIL") or "")
    password = str(
        environ.get("TINYMRP_ADMIN_PASSWORD") or environ.get("DEFAULT_ADMIN_PASSWORD") or ""
    )
    try:
        return validate_first_admin_credentials(email, password)
    except BootstrapConfigurationError as exc:
        # Environment-specific names make entrypoint failures directly actionable.
        message = str(exc).replace("Administrator email", "TINYMRP_ADMIN_EMAIL")
        message = message.replace("Administrator password", "TINYMRP_ADMIN_PASSWORD")
        raise BootstrapConfigurationError(message) from exc


def bootstrap_container(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Reconcile canonical roles and optionally create the very first admin.

    Existing users are deliberately never changed. This matters for guided VPS
    instances, whose persisted environment keeps first-user seeding enabled on
    every restart and update.
    """

    environ = os.environ if environ is None else environ
    seed_admin = _parse_seed_admin(environ)
    user_count = User.objects.count()

    credentials: tuple[str, str] | None = None
    if seed_admin and user_count == 0:
        # Validate all operator input before writing roles or a user.
        credentials = _admin_credentials(environ)

    role_report = reconcile_standard_roles()
    result: dict[str, Any] = {
        "admin": "disabled",
        "roles_created": list(role_report["created"]),
        "roles_drifted": list(role_report["drifted"]),
    }

    if not seed_admin:
        return result
    if user_count:
        result["admin"] = "existing-users-skip"
        return result

    email, password = credentials or ("", "")
    administrator = Role.objects(name=ADMIN_ROLE_SLUG).first()
    if administrator is None:
        raise RuntimeError("Canonical administrator role reconciliation failed.")

    now = utc_now()
    User(
        email=email,
        password=hash_password(password),
        active=True,
        fs_uniquifier=secrets.token_hex(16),
        roles=[administrator],
        password_changed_at=now,
        updated_at=now,
    ).save()
    result["admin"] = "created"
    result["admin_email"] = email
    return result


def main() -> int:
    """Run container bootstrap and return a retry-aware process exit code."""

    try:
        from app import create_app

        app = create_app()
        with app.app_context():
            result = bootstrap_container()
    except BootstrapConfigurationError as exc:
        print(f"[bootstrap] configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - exercised by container smoke
        # Do not render exception values: database URIs and driver errors may
        # contain credentials. The exception type is enough for retry logs.
        print(f"[bootstrap] failed: {type(exc).__name__}", file=sys.stderr)
        return 3

    print(f"[bootstrap] {json.dumps(result, sort_keys=True)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - module entrypoint
    raise SystemExit(main())
