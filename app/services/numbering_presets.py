from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.numbering import NumberingScheme
from app.services.timezone_utils import utc_now


PRESETS = [
    {
        "name": "Default: PART-SEQ6",
        "pattern_segments": [
            {"kind": "literal", "value": "PART"},
            {"kind": "seq", "padding": 6, "base": 10, "start_at": 1, "auto_counter": True},
        ],
        "separator": "-",
        "scope_mode": "global",
        "seq": {"padding": 6, "base": 10, "start_at": 1, "reset_policy": "never"},
        "revision": {"policy": "alpha", "start": "A"},
        "validation_rules": {"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        "is_preset": True,
        "is_recommended": True,
        "visibility": "quickstart",
        "description": "Recommended: PART-SEQ6",
    },
]

LEGACY_PRESET_NAMES = {
    "Preset B: TYPE-YYYY-SEQ5",
    "Preset C: FAM-SUB-SEQ6",
}


def ensure_presets() -> None:
    _remove_legacy_presets()

    preset = PRESETS[0]
    if NumberingScheme.objects().count() == 0:
        NumberingScheme(**preset, is_active=True, audit={"created_at": utc_now()}).save()
        return

    existing = NumberingScheme.objects(name=preset["name"]).first()
    if not existing:
        preset_data = dict(preset)
        has_recommended = NumberingScheme.objects(is_recommended=True, is_active=True).first() is not None
        preset_data["is_recommended"] = not has_recommended
        NumberingScheme(**preset_data, is_active=True, audit={"created_at": utc_now()}).save()
        return

    has_other_recommended = NumberingScheme.objects(
        is_recommended=True,
        is_active=True,
        id__ne=existing.id,
    ).first() is not None
    updates = {
        "name": preset["name"],
        "pattern_segments": preset["pattern_segments"],
        "separator": preset["separator"],
        "scope_mode": preset["scope_mode"],
        "scope_keys": preset.get("scope_keys", []),
        "seq": preset["seq"],
        "revision": preset["revision"],
        "validation_rules": preset["validation_rules"],
        "is_active": True,
        "is_preset": preset["is_preset"],
        "visibility": preset["visibility"],
        "description": preset["description"],
        "is_recommended": not has_other_recommended,
    }
    existing.update(**{f"set__{k}": v for k, v in updates.items()})


def _remove_legacy_presets() -> None:
    if not LEGACY_PRESET_NAMES:
        return

    NumberingScheme.objects(
        is_preset=True,
        name__in=list(LEGACY_PRESET_NAMES),
    ).delete()


def get_recommended_scheme() -> Optional[NumberingScheme]:
    scheme = NumberingScheme.objects(is_recommended=True, is_active=True).first()
    if scheme:
        return scheme
    scheme = NumberingScheme.objects(is_preset=True, is_active=True).first()
    if scheme:
        return scheme
    return NumberingScheme.objects(is_active=True).first()
