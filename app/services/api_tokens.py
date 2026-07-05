from __future__ import annotations

from datetime import datetime, timedelta
import base64
import hmac
import hashlib
import os
from typing import Optional, Tuple

from flask import current_app, has_app_context
from mongoengine.errors import NotUniqueError

from app.models.api_token import ApiToken
from app.models.auth import User
from app.services.timezone_utils import utc_now

TOKEN_PREFIX = "tmrp_"
TOKEN_BYTES = 32
LAST_USED_MINUTES = 10


def _pepper() -> str:
    if has_app_context():
        return (current_app.config.get("SECRET_KEY") or current_app.config.get("SECURITY_PASSWORD_SALT") or "").strip()
    return (os.environ.get("SECRET_KEY") or os.environ.get("SECURITY_PASSWORD_SALT") or "").strip()


def _hash_token(raw_token: str) -> str:
    secret = _pepper().encode("utf-8")
    msg = raw_token.encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def _random_token() -> str:
    raw = base64.urlsafe_b64encode(os.urandom(TOKEN_BYTES)).decode("utf-8").rstrip("=")
    return TOKEN_PREFIX + raw


def create_token(user: User, label: str = "", expires_at: Optional[datetime] = None) -> Tuple[ApiToken, str]:
    for _ in range(5):
        raw = _random_token()
        token_hash = _hash_token(raw)
        doc = ApiToken(
            user_id=user,
            token_hash=token_hash,
            label=label or "",
            expires_at=expires_at,
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
    return token


_last_used_cache = {}


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
