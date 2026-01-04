from datetime import datetime

from app.models.numbering import NumberingScheme
from app.services.numbering import (
    allocate_number,
    bucket_for_reset_policy,
    normalize_scheme_payload,
    revision_for_existing,
    validate_scheme_definition,
)


def test_validate_requires_seq_segment():
    payload = {
        "name": "NoSeq",
        "pattern_segments": [{"kind": "literal", "value": "ASM"}],
    }
    scheme, errors = normalize_scheme_payload(payload, "user@example.com", None)
    assert not errors
    v_errors, _, _ = validate_scheme_definition(scheme)
    assert any("seq" in e for e in v_errors)


def test_allocate_increments_sequence():
    scheme = NumberingScheme(
        name="TypeSeq",
        pattern_segments=[
            {"kind": "field", "field": "type", "casing": "upper"},
            {"kind": "seq", "padding": 3, "base": 10},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 3, "base": 10, "start_at": 1, "reset_policy": "never"},
        revision={"policy": "alpha", "start": "A"},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": datetime.utcnow()},
    ).save()

    result1, errors1 = allocate_number(
        scheme,
        {"type": "asm"},
        create_part_if_missing=False,
        requested_revision_action="new_part",
        existing_part_number=None,
        user_email=None,
        cad_ref=None,
    )
    result2, errors2 = allocate_number(
        scheme,
        {"type": "asm"},
        create_part_if_missing=False,
        requested_revision_action="new_part",
        existing_part_number=None,
        user_email=None,
        cad_ref=None,
    )

    assert not errors1
    assert not errors2
    assert result1["part_number"] != result2["part_number"]
    assert result1["part_number"].endswith("001")
    assert result2["part_number"].endswith("002")


def test_revision_increment_policies():
    assert revision_for_existing("A", "alpha", "A") == "B"
    assert revision_for_existing("Z", "alpha", "A") == "AA"
    assert revision_for_existing("", "alpha", "A") == "A"
    assert revision_for_existing("01", "numeric", "01") == "02"
    assert revision_for_existing("", "numeric", "01") == "02"


def test_reset_bucket_behavior():
    now = datetime(2026, 1, 15, 10, 30, 0)
    yearly, errors = bucket_for_reset_policy("yearly", {}, now)
    assert not errors
    assert yearly == "2026"

    monthly, errors = bucket_for_reset_policy("monthly", {}, now)
    assert not errors
    assert monthly == "2026-01"

    by_project, errors = bucket_for_reset_policy("by_project", {"project": "alpha"}, now)
    assert not errors
    assert by_project == "ALPHA"
