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
    """Seed the built-in scheme when missing. Existing schemes are never force-reset:
    boot-time resets silently reverted user changes and re-enabled disabled schemes."""
    preset = DEFAULT_PRESET
    existing = NumberingScheme.objects(name=preset["name"]).first()
    if existing is None:
        preset_data = dict(preset)
        has_recommended = NumberingScheme.objects(is_recommended=True, is_active=True).first() is not None
        preset_data["is_recommended"] = bool(preset_data.get("is_recommended")) and not has_recommended
        NumberingScheme(**preset_data, is_active=True, audit={"created_at": utc_now()}).save()
        return

    # One-time migration: earlier seeds forced revision "A" onto every new part. If the
    # preset still carries that seeded default, switch it to "no revision". Any other
    # policy/start combination is a deliberate choice and is left alone.
    revision = existing.revision or {}
    if (
        str(revision.get("policy") or "").strip().lower() == "alpha"
        and str(revision.get("start") or "").strip().upper() == "A"
    ):
        existing.update(set__revision=dict(preset["revision"]))


def get_recommended_scheme() -> Optional[NumberingScheme]:
    scheme = NumberingScheme.objects(is_recommended=True, is_active=True).first()
    if scheme:
        return scheme
    scheme = NumberingScheme.objects(is_preset=True, is_active=True).first()
    if scheme:
        return scheme
    return NumberingScheme.objects(is_active=True).first()
