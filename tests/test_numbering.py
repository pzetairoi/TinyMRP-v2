from datetime import datetime

from app.models.numbering import NumberingScheme
from app.services.numbering import (
    allocate_number,
    bucket_for_reset_policy,
    normalize_scheme_payload,
    revision_for_existing,
    validate_scheme_definition,
)
from app.services.numbering_presets import ensure_presets
from concurrent.futures import ThreadPoolExecutor


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


def test_concurrent_allocate_unique():
    scheme = NumberingScheme(
        name="ConcurrentSeq",
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

    def alloc():
        result, errors = allocate_number(
            scheme,
            {"type": "asm"},
            create_part_if_missing=False,
            requested_revision_action="new_part",
            existing_part_number=None,
            user_email=None,
            cad_ref=None,
        )
        assert not errors
        return result["part_number"]

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _: alloc(), range(10)))

    assert len(results) == len(set(results))


def test_validate_simple_literal_seq_scheme_with_start_at():
    payload = {
        "name": "PartSeq",
        "separator": "-",
        "seq": {"padding": 3, "base": 10, "start_at": 12, "reset_policy": "never"},
        "pattern_segments": [
            {"kind": "literal", "value": "PART"},
            {"kind": "seq", "padding": 3, "base": 10},
        ],
    }
    scheme, errors = normalize_scheme_payload(payload, "user@example.com", None)
    assert not errors
    v_errors, _, example = validate_scheme_definition(scheme)
    assert not v_errors
    assert example["part_number_example"] == "PART-012"


def test_validate_multi_sequence_requires_exactly_one_automatic_segment():
    payload = {
        "name": "DualSeqInvalid",
        "separator": "-",
        "seq": {"padding": 3, "base": 10, "start_at": 1, "reset_policy": "never"},
        "pattern_segments": [
            {"kind": "literal", "value": "PART"},
            {"kind": "seq", "padding": 3, "base": 10, "start_at": 1},
            {"kind": "seq", "padding": 3, "base": 10, "start_at": 7},
        ],
    }

    scheme, errors = normalize_scheme_payload(payload, "user@example.com", None)
    assert not errors
    v_errors, _, _ = validate_scheme_definition(scheme)

    assert any("Exactly one seq segment" in error for error in v_errors)


def test_allocate_multi_sequence_only_increments_automatic_segment():
    scheme = NumberingScheme(
        name="DualSeqAuto",
        pattern_segments=[
            {"kind": "literal", "value": "PART"},
            {"kind": "seq", "padding": 2, "base": 10, "auto_counter": True},
            {"kind": "seq", "padding": 2, "base": 10, "start_at": 7},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 2, "base": 10, "start_at": 1, "reset_policy": "never"},
        revision={"policy": "alpha", "start": "A"},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": datetime.utcnow()},
    ).save()

    result1, errors1 = allocate_number(
        scheme,
        {},
        create_part_if_missing=False,
        requested_revision_action="new_part",
        existing_part_number=None,
        user_email=None,
        cad_ref=None,
    )
    result2, errors2 = allocate_number(
        scheme,
        {},
        create_part_if_missing=False,
        requested_revision_action="new_part",
        existing_part_number=None,
        user_email=None,
        cad_ref=None,
    )

    assert not errors1
    assert not errors2
    assert result1["part_number"] == "PART-01-07"
    assert result2["part_number"] == "PART-02-07"
    assert result1["sequence_values_used"] == [1, 7]
    assert result2["sequence_values_used"] == [2, 7]
    assert result1["auto_sequence_index"] == 0


def test_allocate_multi_sequence_accepts_manual_sequence_override():
    scheme = NumberingScheme(
        name="DualSeqOverride",
        pattern_segments=[
            {"kind": "literal", "value": "PART"},
            {"kind": "seq", "padding": 2, "base": 10, "auto_counter": True},
            {"kind": "seq", "padding": 2, "base": 10, "start_at": 7},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 2, "base": 10, "start_at": 1, "reset_policy": "never"},
        revision={"policy": "alpha", "start": "A"},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": datetime.utcnow()},
    ).save()

    result, errors = allocate_number(
        scheme,
        {},
        create_part_if_missing=False,
        requested_revision_action="new_part",
        existing_part_number=None,
        user_email=None,
        cad_ref=None,
        sequence_values=[1, 12],
    )

    assert not errors
    assert result["part_number"] == "PART-01-12"
    assert result["sequence_values_used"] == [1, 12]


def test_ensure_presets_seeds_simple_recommended_scheme():
    ensure_presets()

    scheme = NumberingScheme.objects(name="Default: PART-SEQ6").first()
    assert scheme is not None
    assert scheme.is_recommended is True
    assert NumberingScheme.objects(is_preset=True).count() == 1
    assert [segment.get("kind") for segment in scheme.pattern_segments] == ["literal", "seq"]
    assert scheme.pattern_segments[0].get("value") == "PART"
    assert scheme.pattern_segments[1].get("auto_counter") is True


def test_ensure_presets_removes_legacy_seeded_presets():
    NumberingScheme(
        name="Preset B: TYPE-YYYY-SEQ5",
        is_active=True,
        is_preset=True,
        pattern_segments=[
            {"kind": "field", "field": "type", "casing": "upper"},
            {"kind": "date", "fmt": "YYYY"},
            {"kind": "seq", "padding": 5, "base": 10},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 5, "base": 10, "start_at": 1, "reset_policy": "yearly"},
        revision={"policy": "alpha", "start": "A"},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": datetime.utcnow()},
    ).save()
    NumberingScheme(
        name="Preset C: FAM-SUB-SEQ6",
        is_active=True,
        is_preset=True,
        pattern_segments=[
            {"kind": "field", "field": "family", "casing": "upper"},
            {"kind": "field", "field": "subfamily", "casing": "upper"},
            {"kind": "seq", "padding": 6, "base": 10},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 6, "base": 10, "start_at": 1, "reset_policy": "never"},
        revision={"policy": "alpha", "start": "A"},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": datetime.utcnow()},
    ).save()

    ensure_presets()

    assert NumberingScheme.objects(name="Preset B: TYPE-YYYY-SEQ5").first() is None
    assert NumberingScheme.objects(name="Preset C: FAM-SUB-SEQ6").first() is None
    assert NumberingScheme.objects(name="Default: PART-SEQ6").first() is not None


def test_ensure_presets_does_not_add_duplicate_recommended_scheme():
    NumberingScheme(
        name="Existing Recommended",
        is_active=True,
        is_recommended=True,
        pattern_segments=[
            {"kind": "literal", "value": "EXISTING"},
            {"kind": "seq", "padding": 3, "base": 10},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 3, "base": 10, "start_at": 1, "reset_policy": "never"},
        revision={"policy": "alpha", "start": "A"},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": datetime.utcnow()},
    ).save()

    ensure_presets()

    recommended = list(NumberingScheme.objects(is_recommended=True))
    assert len(recommended) == 1
    assert recommended[0].name == "Existing Recommended"
