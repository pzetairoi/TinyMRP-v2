from __future__ import annotations

import re
from typing import Iterable

from app.models.auth import User
from app.models.user_settings import UserSettings


PROFILE_COLOR_CHOICES: list[dict[str, str]] = [
    {"value": "#1d4ed8", "label": "Blue"},
    {"value": "#0f766e", "label": "Teal"},
    {"value": "#166534", "label": "Green"},
    {"value": "#a16207", "label": "Amber"},
    {"value": "#be123c", "label": "Rose"},
    {"value": "#7c3aed", "label": "Violet"},
    {"value": "#475569", "label": "Slate"},
    {"value": "#7f1d1d", "label": "Brick"},
]

PROFILE_SHAPE_CHOICES: list[dict[str, str]] = [
    {"value": "circle", "label": "Circle"},
    {"value": "rounded", "label": "Rounded"},
    {"value": "square", "label": "Square"},
]

_DEFAULT_COLOR = PROFILE_COLOR_CHOICES[0]["value"]
_DEFAULT_SHAPE = PROFILE_SHAPE_CHOICES[0]["value"]


def role_names_for_user(user) -> list[str]:
    names = set()
    for role in (getattr(user, "roles", []) or []):
        name = str(getattr(role, "name", "") or "").strip()
        if name:
            names.add(name)
    return sorted(names)


def permissions_for_user(user) -> list[str]:
    perms = set()
    for role in (getattr(user, "roles", []) or []):
        for perm in (getattr(role, "permissions", []) or []):
            text = str(perm or "").strip()
            if text:
                perms.add(text)
    return sorted(perms)


def default_profile_settings() -> dict[str, str]:
    return {
        "display_name": "",
        "avatar_color": _DEFAULT_COLOR,
        "avatar_shape": _DEFAULT_SHAPE,
    }


def profile_color_choices() -> list[dict[str, str]]:
    return [dict(item) for item in PROFILE_COLOR_CHOICES]


def profile_shape_choices() -> list[dict[str, str]]:
    return [dict(item) for item in PROFILE_SHAPE_CHOICES]


def sanitize_profile(payload: dict | None) -> dict[str, str]:
    raw = dict(payload or {})
    allowed_colors = {item["value"] for item in PROFILE_COLOR_CHOICES}
    allowed_shapes = {item["value"] for item in PROFILE_SHAPE_CHOICES}
    display_name = " ".join(str(raw.get("display_name") or "").strip().split())
    if len(display_name) > 60:
        display_name = display_name[:60].rstrip()
    avatar_color = str(raw.get("avatar_color") or _DEFAULT_COLOR).strip()
    if avatar_color not in allowed_colors:
        avatar_color = _DEFAULT_COLOR
    avatar_shape = str(raw.get("avatar_shape") or _DEFAULT_SHAPE).strip().lower()
    if avatar_shape not in allowed_shapes:
        avatar_shape = _DEFAULT_SHAPE
    return {
        "display_name": display_name,
        "avatar_color": avatar_color,
        "avatar_shape": avatar_shape,
    }


def _initial_tokens(text: str) -> list[str]:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", " ", str(text or "").strip())
    tokens = [token for token in re.split(r"[._\s-]+", cleaned) if token]
    return tokens


def initials_for_label(text: str) -> str:
    tokens = _initial_tokens(text)
    if not tokens:
        return "U"
    if len(tokens) == 1:
        token = tokens[0]
        return token[:2].upper() if len(token) > 1 else token.upper()
    return (tokens[0][0] + tokens[1][0]).upper()


def profile_for_user(user, settings: UserSettings | None = None) -> dict[str, object]:
    settings = settings or UserSettings.objects(user_id=user).first()
    raw_profile = {}
    if settings is not None and isinstance(getattr(settings, "profile", None), dict):
        raw_profile = settings.profile or {}
    profile = sanitize_profile(raw_profile)
    email = str(getattr(user, "email", "") or "").strip()
    label = profile["display_name"] or email or "User"
    return {
        "email": email,
        "display_name": profile["display_name"],
        "label": label,
        "initials": initials_for_label(profile["display_name"] or email or "User"),
        "avatar_color": profile["avatar_color"],
        "avatar_shape": profile["avatar_shape"],
        "roles": role_names_for_user(user),
        "permissions": permissions_for_user(user),
    }


def fallback_profile(identifier: str | None) -> dict[str, object]:
    text = str(identifier or "").strip()
    label = text or "Unknown"
    profile = default_profile_settings()
    return {
        "email": text,
        "display_name": "",
        "label": label,
        "initials": initials_for_label(label),
        "avatar_color": profile["avatar_color"],
        "avatar_shape": profile["avatar_shape"],
        "roles": [],
        "permissions": [],
    }


def resolve_identity_profiles(identifiers: Iterable[str | None]) -> dict[str, dict[str, object]]:
    normalized = []
    for identifier in identifiers:
        text = str(identifier or "").strip()
        if text:
            normalized.append(text)
    if not normalized:
        return {}

    lowered = {text.lower(): text for text in normalized}
    users = {
        str(user.email or "").strip().lower(): user
        for user in User.objects(email__in=[text for text in lowered.values()]).only("email")
    }
    settings_by_user = {
        str(settings.user_id.id): settings
        for settings in UserSettings.objects(user_id__in=[user.id for user in users.values()])
    }

    out: dict[str, dict[str, object]] = {}
    for key, original in lowered.items():
        user = users.get(key)
        if user is not None:
            out[key] = profile_for_user(user, settings_by_user.get(str(user.id)))
        else:
            out[key] = fallback_profile(original)
    return out


def resolve_identity_profile(identifier: str | None) -> dict[str, object]:
    text = str(identifier or "").strip()
    if not text:
        return fallback_profile("")
    return resolve_identity_profiles([text]).get(text.lower(), fallback_profile(text))
