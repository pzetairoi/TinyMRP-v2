from __future__ import annotations

from flask import current_app
from flask_security.utils import verify_password


def password_policy_summary() -> dict[str, int]:
    min_length = int(current_app.config.get("SECURITY_PASSWORD_LENGTH_MIN") or 12)
    return {
        "min_length": max(8, min_length),
        "max_length": 128,
    }


def validate_password_change(
    *,
    current_password: str,
    current_password_hash: str,
    new_password: str,
    confirm_password: str,
    email: str = "",
) -> list[str]:
    errors: list[str] = []
    policy = password_policy_summary()
    current_password = str(current_password or "")
    new_password = str(new_password or "")
    confirm_password = str(confirm_password or "")
    email = str(email or "").strip().lower()

    if not current_password:
        errors.append("Current password is required.")
    elif not verify_password(current_password, current_password_hash):
        errors.append("Current password is incorrect.")

    if not new_password:
        errors.append("New password is required.")
    if not confirm_password:
        errors.append("Password confirmation is required.")
    if new_password and confirm_password and new_password != confirm_password:
        errors.append("Password confirmation does not match.")
    if new_password:
        if len(new_password) < policy["min_length"]:
            errors.append(f"New password must be at least {policy['min_length']} characters long.")
        if len(new_password) > policy["max_length"]:
            errors.append(f"New password must be no more than {policy['max_length']} characters long.")
        if verify_password(new_password, current_password_hash):
            errors.append("New password must be different from the current password.")
        if email and new_password.strip().lower() == email:
            errors.append("New password must not match the account email.")
    return errors


def validate_admin_password(password: str, *, email: str = "") -> list[str]:
    errors: list[str] = []
    policy = password_policy_summary()
    password = str(password or "")
    email = str(email or "").strip().lower()

    if not password:
        errors.append("Password is required.")
        return errors
    if len(password) < policy["min_length"]:
        errors.append(f"Password must be at least {policy['min_length']} characters long.")
    if len(password) > policy["max_length"]:
        errors.append(f"Password must be no more than {policy['max_length']} characters long.")
    if email and password.strip().lower() == email:
        errors.append("Password must not match the account email.")
    return errors
