from __future__ import annotations

from datetime import datetime, timedelta
import base64
import hmac
import hashlib
import os
from typing import Optional, Tuple

from flask import current_app, has_app_context
from mongoengine.errors import DoesNotExist, NotUniqueError, ValidationError
from mongoengine.queryset.visitor import Q

from app.models.api_token import ApiToken
from app.models.auth import User
from app.services.timezone_utils import as_utc_naive, utc_now

TOKEN_PREFIX = "tmrp_"
TOKEN_BYTES = 32
LAST_USED_MINUTES = 10
DEFAULT_TOKEN_TTL_DAYS = 90
MAX_TOKEN_TTL_DAYS = 365
MAX_TOKEN_LABEL_LENGTH = 120


class TokenPolicyError(ValueError):
    """Raised when token creation or rotation violates lifecycle policy."""


def _pepper() -> str:
    if has_app_context():
        return (
            current_app.config.get("SECRET_KEY")
            or current_app.config.get("SECURITY_PASSWORD_SALT")
            or ""
        ).strip()
    return (os.environ.get("SECRET_KEY") or os.environ.get("SECURITY_PASSWORD_SALT") or "").strip()


def _hash_token(raw_token: str) -> str:
    secret = _pepper().encode("utf-8")
    msg = raw_token.encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def _random_token() -> str:
    raw = base64.urlsafe_b64encode(os.urandom(TOKEN_BYTES)).decode("utf-8").rstrip("=")
    return TOKEN_PREFIX + raw


def token_policy() -> dict[str, int]:
    def _positive_int(name: str, fallback: int) -> int:
        value = (
            current_app.config.get(name, fallback)
            if has_app_context()
            else os.environ.get(name, fallback)
        )
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise TokenPolicyError(f"{name} must be a positive integer.") from exc
        if parsed < 1:
            raise TokenPolicyError(f"{name} must be a positive integer.")
        return parsed

    default_days = _positive_int("API_TOKEN_DEFAULT_TTL_DAYS", DEFAULT_TOKEN_TTL_DAYS)
    max_days = _positive_int("API_TOKEN_MAX_TTL_DAYS", MAX_TOKEN_TTL_DAYS)
    if default_days > max_days:
        raise TokenPolicyError("API_TOKEN_DEFAULT_TTL_DAYS cannot exceed API_TOKEN_MAX_TTL_DAYS.")
    return {"default_ttl_days": default_days, "max_ttl_days": max_days}


def _expiry_for_creation(
    *, expires_at: Optional[datetime] = None, lifetime_days: Optional[int] = None
) -> datetime:
    if expires_at is not None and lifetime_days is not None:
        raise TokenPolicyError("Specify either expires_at or lifetime_days, not both.")

    policy = token_policy()
    now = utc_now()
    if lifetime_days is None and expires_at is None:
        lifetime_days = policy["default_ttl_days"]

    if lifetime_days is not None:
        try:
            lifetime_days = int(lifetime_days)
        except (TypeError, ValueError) as exc:
            raise TokenPolicyError("Token lifetime must be a whole number of days.") from exc
        if lifetime_days < 1 or lifetime_days > policy["max_ttl_days"]:
            raise TokenPolicyError(
                f"Token lifetime must be between 1 and {policy['max_ttl_days']} days."
            )
        return now + timedelta(days=lifetime_days)

    normalized_expiry = as_utc_naive(expires_at)
    if normalized_expiry is None or normalized_expiry <= now:
        raise TokenPolicyError("Token expiry must be in the future.")
    if normalized_expiry > now + timedelta(days=policy["max_ttl_days"]):
        raise TokenPolicyError(
            f"Token expiry cannot be more than {policy['max_ttl_days']} days away."
        )
    return normalized_expiry


def _active_owner(user: User) -> Optional[User]:
    if user is None or getattr(user, "id", None) is None:
        return None
    try:
        return User.objects(id=user.id, active=True).first()
    except (DoesNotExist, ValidationError):
        return None


def create_token(
    user: User,
    label: str = "",
    expires_at: Optional[datetime] = None,
    *,
    lifetime_days: Optional[int] = None,
) -> Tuple[ApiToken, str]:
    owner = _active_owner(user)
    if owner is None:
        raise TokenPolicyError("API tokens can only be created for an active user.")
    normalized_label = str(label or "").strip()
    if len(normalized_label) > MAX_TOKEN_LABEL_LENGTH:
        raise TokenPolicyError(f"Token label cannot exceed {MAX_TOKEN_LABEL_LENGTH} characters.")
    resolved_expiry = _expiry_for_creation(
        expires_at=expires_at,
        lifetime_days=lifetime_days,
    )
    for _ in range(5):
        raw = _random_token()
        token_hash = _hash_token(raw)
        doc = ApiToken(
            user_id=owner,
            token_hash=token_hash,
            label=normalized_label,
            expires_at=resolved_expiry,
        )
        try:
            doc.save()
            return doc, raw
        except NotUniqueError:
            continue
    raise RuntimeError("Unable to create a unique token.")


def verify_token(raw_token: str) -> Optional[ApiToken]:
    if not raw_token:
        return None
    token_hash = _hash_token(raw_token)
    token = ApiToken.objects(token_hash=token_hash).first()
    if not token:
        return None
    if token.revoked_at is not None:
        return None
    if token.expires_at and token.expires_at <= utc_now():
        return None
    try:
        owner = token.user_id
    except (DoesNotExist, ValidationError):
        owner = None
    if owner is None:
        revoke_token(token, reason="owner_missing")
        return None
    try:
        owner = User.objects(id=owner.id, active=True).first()
    except (DoesNotExist, ValidationError):
        owner = None
    if owner is None:
        revoke_token(token, reason="owner_inactive")
        return None
    return token


def token_status(token: ApiToken, *, now: Optional[datetime] = None) -> str:
    if token.revoked_at is not None:
        return "revoked"
    if token.expires_at is None:
        return "legacy_no_expiry"
    if token.expires_at <= (now or utc_now()):
        return "expired"
    return "active"


def revoke_token(token: ApiToken, *, reason: str = "explicit") -> bool:
    if token is None or getattr(token, "id", None) is None:
        return False
    revoked_at = utc_now()
    normalized_reason = str(reason or "explicit")[:80]
    changed = ApiToken.objects(id=token.id, revoked_at=None).update_one(
        set__revoked_at=revoked_at,
        set__revocation_reason=normalized_reason,
    )
    if changed:
        token.revoked_at = revoked_at
        token.revocation_reason = normalized_reason
    return bool(changed)


def revoke_user_tokens(user: User, *, reason: str) -> int:
    if user is None or getattr(user, "id", None) is None:
        return 0
    return int(
        ApiToken.objects(user_id=user, revoked_at=None).update(
            set__revoked_at=utc_now(),
            set__revocation_reason=str(reason or "security_event")[:80],
        )
    )


def revoke_all_tokens(*, reason: str = "administrator_global_logout") -> int:
    now = utc_now()
    active_query = Q(revoked_at=None) & (Q(expires_at=None) | Q(expires_at__gt=now))
    return int(
        ApiToken.objects(active_query).update(
            set__revoked_at=now,
            set__revocation_reason=str(reason or "administrator_global_logout")[:80],
        )
    )


def rotate_token(
    token: ApiToken,
    user: User,
    *,
    lifetime_days: Optional[int] = None,
) -> Tuple[ApiToken, str]:
    owner = _active_owner(user)
    if owner is None:
        raise TokenPolicyError("API tokens can only be rotated by an active user.")
    try:
        token_owner_id = str(token.user_id.id)
    except (AttributeError, DoesNotExist, ValidationError) as exc:
        raise TokenPolicyError("Token owner no longer exists.") from exc
    if token_owner_id != str(owner.id):
        raise TokenPolicyError("Token does not belong to this user.")
    if token_status(token) != "active" and token_status(token) != "legacy_no_expiry":
        raise TokenPolicyError("Only an active token can be rotated.")

    replacement, raw = create_token(
        owner,
        token.label or "",
        lifetime_days=lifetime_days,
    )
    changed = ApiToken.objects(id=token.id, revoked_at=None).update_one(
        set__revoked_at=utc_now(),
        set__revocation_reason="rotated",
    )
    if not changed:
        revoke_token(replacement, reason="concurrent_rotation_lost")
        raise TokenPolicyError("Token was already revoked or rotated.")
    token.reload()
    return replacement, raw


_last_used_cache: dict[str, datetime] = {}


def touch_last_used(token: ApiToken) -> None:
    if not token:
        return
    now = utc_now()
    token_id = str(token.id)
    last = _last_used_cache.get(token_id)
    if last and now - last < timedelta(minutes=LAST_USED_MINUTES):
        return
    ApiToken.objects(id=token.id).update_one(set__last_used_at=now)
    _last_used_cache[token_id] = now
