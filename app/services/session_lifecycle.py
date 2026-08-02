"""Server-side browser-session invalidation.

Flask-Security stores ``User.fs_uniquifier`` in every authenticated browser
session and resolves the user by that value on each request. Rotating it is a
small, durable session-version change: every previously issued session and
remember cookie stops resolving, while the user's database identity is stable.
"""

from __future__ import annotations

import secrets
from typing import Any

from mongoengine.errors import NotUniqueError

from app.models.auth import User
from app.services.timezone_utils import utc_now


def revoke_user_sessions(user: User, *, reason: str) -> bool:
    """Invalidate all existing browser sessions for a persisted user.

    The compare-and-set update avoids overwriting a concurrent rotation. If a
    second security event wins the race, this function reloads and rotates the
    new value as well. No session identifier is written to the audit log.
    """

    user_id = getattr(user, "id", None)
    if user_id is None:
        raise ValueError("Cannot revoke sessions for an unsaved user")

    normalized_reason = str(reason or "").strip()
    if not normalized_reason:
        raise ValueError("Session revocation reason is required")

    for _attempt in range(5):
        previous = str(getattr(user, "fs_uniquifier", "") or "")
        replacement = secrets.token_hex(32)
        changed_at = utc_now()
        try:
            updated = User.objects(
                id=user_id,
                fs_uniquifier=previous,
            ).update_one(
                set__fs_uniquifier=replacement,
                set__updated_at=changed_at,
            )
        except NotUniqueError:
            continue

        if updated:
            user.fs_uniquifier = replacement
            user.updated_at = changed_at
            try:
                from app.services.audit import log_action

                log_action(
                    "session.security_event_revoke",
                    resource_type="user",
                    resource=str(getattr(user, "email", "") or ""),
                    meta={
                        "reason": normalized_reason[:120],
                        "mechanism": "fs_uniquifier_rotation",
                    },
                )
            except Exception:
                # Session invalidation is the primary security operation; audit
                # failures are already surfaced by the audit service/logger.
                pass
            return True

        try:
            user.reload()
        except Exception as exc:
            raise RuntimeError("User disappeared during session revocation") from exc

    raise RuntimeError("Could not rotate the browser-session version")


def session_identity(user: Any) -> str:
    """Return the identifier Flask-Security stores in an authenticated session."""

    return str(getattr(user, "fs_uniquifier", "") or "")


def revoke_role_sessions(role: Any, *, reason: str) -> int:
    """Invalidate sessions for every user currently assigned ``role``."""

    role_id = getattr(role, "id", None)
    if role_id is None:
        return 0
    revoked = 0
    for user in User.objects(roles=role_id):
        if revoke_user_sessions(user, reason=reason):
            revoked += 1
    return revoked
