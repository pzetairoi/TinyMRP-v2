from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.numbering import NumberingScheme


PRESETS = [
    {
        "name": "Default: PART-SEQ6",
        "pattern_segments": [
            {"kind": "literal", "value": "PART"},
            {"kind": "seq", "padding": 6, "base": 10},
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
    {
        "name": "Preset B: TYPE-YYYY-SEQ5",
        "pattern_segments": [
            {"kind": "field", "field": "type", "casing": "upper"},
            {"kind": "date", "fmt": "YYYY"},
            {"kind": "seq", "padding": 5, "base": 10},
        ],
        "separator": "-",
        "scope_mode": "global",
        "seq": {"padding": 5, "base": 10, "start_at": 1, "reset_policy": "yearly"},
        "revision": {"policy": "alpha", "start": "A"},
        "validation_rules": {"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        "is_preset": True,
        "is_recommended": False,
        "visibility": "quickstart",
        "description": "TYPE-YYYY-SEQ5",
    },
    {
        "name": "Preset C: FAM-SUB-SEQ6",
        "pattern_segments": [
            {"kind": "field", "field": "family", "casing": "upper"},
            {"kind": "field", "field": "subfamily", "casing": "upper"},
            {"kind": "seq", "padding": 6, "base": 10},
        ],
        "separator": "-",
        "scope_mode": "global",
        "seq": {"padding": 6, "base": 10, "start_at": 1, "reset_policy": "never"},
        "revision": {"policy": "alpha", "start": "A"},
        "validation_rules": {"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        "is_preset": True,
        "is_recommended": False,
        "visibility": "quickstart",
        "description": "FAM-SUB-SEQ6",
    },
]


def ensure_presets() -> None:
    if NumberingScheme.objects().count() == 0:
        for preset in PRESETS:
            NumberingScheme(**preset, is_active=True, audit={"created_at": datetime.utcnow()}).save()
        return

    has_recommended = NumberingScheme.objects(is_recommended=True, is_active=True).first() is not None

    for preset in PRESETS:
        existing = NumberingScheme.objects(name=preset["name"]).first()
        if not existing:
            preset_data = dict(preset)
            if preset_data.get("is_recommended") and has_recommended:
                preset_data["is_recommended"] = False
            elif preset_data.get("is_recommended"):
                has_recommended = True
            NumberingScheme(**preset_data, is_active=True, audit={"created_at": datetime.utcnow()}).save()
            continue

        updates = {
            "is_preset": preset["is_preset"],
            "visibility": preset["visibility"],
            "description": preset["description"],
        }
        if preset["is_recommended"] and not has_recommended:
            updates["is_recommended"] = True
            has_recommended = True
        existing.update(**{f"set__{k}": v for k, v in updates.items()})


def get_recommended_scheme() -> Optional[NumberingScheme]:
    scheme = NumberingScheme.objects(is_recommended=True, is_active=True).first()
    if scheme:
        return scheme
    scheme = NumberingScheme.objects(is_preset=True, is_active=True).first()
    if scheme:
        return scheme
    return NumberingScheme.objects(is_active=True).first()
