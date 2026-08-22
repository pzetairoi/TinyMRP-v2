from __future__ import annotations

from typing import Optional

from app.models.numbering import NumberingScheme
from app.services.timezone_utils import utc_now


# The single built-in scheme. New parts get no revision by default; users who want
# revision letters or numbers can opt in from the scheme builder.
DEFAULT_PRESET = {
    "name": "Default: PART-SEQ6",
    "pattern_segments": [
        {"kind": "literal", "value": "PART"},
        {"kind": "seq", "padding": 6, "base": 10, "start_at": 1, "auto_counter": True},
    ],
    "separator": "-",
    "scope_mode": "global",
    "seq": {"padding": 6, "base": 10, "start_at": 1, "reset_policy": "never"},
    "revision": {"policy": "none", "start": ""},
    "validation_rules": {"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
    "is_preset": True,
    "is_recommended": True,
    "visibility": "quickstart",
    "description": "Recommended: PART-000001, no revision",
}


def ensure_presets() -> None:
    """Seed the built-in scheme ONCE, into a database that has no scheme yet.

    This used to seed whenever the scheme was missing, so deleting it only lasted
    until the next restart - it kept coming back (issue #98). Seeding is a
    first-run convenience, not a promise that this scheme exists: an
    administrator who deletes it has decided it should be gone, and that decision
    now sticks.

    Nothing is gridlocked by an empty list. Copying an existing scheme is only
    one way to start; the builder's "Start from" defaults to Blank, so a new
    scheme can always be created with no scheme to copy.

    Existing schemes are still never force-reset: boot-time resets silently
    reverted user changes and re-enabled disabled schemes.
    """
    from app.services.app_settings import get_app_settings

    settings = get_app_settings()
    if settings is not None and settings.numbering_preset_seeded:
        return

    preset = DEFAULT_PRESET
    existing = NumberingScheme.objects(name=preset["name"]).first()
    if existing is None:
        # Only into a genuinely empty database. A database that already holds
        # schemes has been set up, so a missing built-in scheme there means it
        # was deleted on purpose.
        if NumberingScheme.objects.first() is None:
            preset_data = dict(preset)
            NumberingScheme(**preset_data, is_active=True, audit={"created_at": utc_now()}).save()
    else:
        # One-time migration: earlier seeds forced revision "A" onto every new part. If
        # the preset still carries that seeded default, switch it to "no revision". Any
        # other policy/start combination is a deliberate choice and is left alone.
        revision = existing.revision or {}
        if (
            str(revision.get("policy") or "").strip().lower() == "alpha"
            and str(revision.get("start") or "").strip().upper() == "A"
        ):
            existing.update(set__revision=dict(preset["revision"]))

    if settings is not None:
        settings.update(set__numbering_preset_seeded=True)


def get_recommended_scheme() -> Optional[NumberingScheme]:
    scheme = NumberingScheme.objects(is_recommended=True, is_active=True).first()
    if scheme:
        return scheme
    scheme = NumberingScheme.objects(is_preset=True, is_active=True).first()
    if scheme:
        return scheme
    return NumberingScheme.objects(is_active=True).first()
