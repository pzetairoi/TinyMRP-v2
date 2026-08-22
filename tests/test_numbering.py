from datetime import datetime

from app.models.numbering import NumberingScheme
from app.models.part import Part
from app.services.numbering import (
    allocate_number,
    bucket_for_reset_policy,
    normalize_scheme_payload,
    preview_number,
    revision_for_existing,
    validate_scheme_definition,
)
from app.services.numbering_presets import ensure_presets
from app.services.timezone_utils import utc_now
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
            {"kind": "literal", "value": "ASM"},
            {"kind": "seq", "padding": 3, "base": 10},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 3, "base": 10, "start_at": 1, "reset_policy": "never"},
        revision={"policy": "alpha", "start": "A"},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": utc_now()},
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


def test_preview_reports_last_part_number_used_for_scheme():
    scheme = _simple_auto_scheme("LastUsedScheme")
    first = _alloc(scheme)
    second = _alloc(scheme)

    preview, errors = preview_number(scheme, {})

    assert not errors
    assert first != second
    assert preview["last_part_number"] == second


def test_allocate_without_revision_config_yields_empty_revision():
    # A scheme that never configured a revision policy must not invent "A":
    # new parts stay revision-less and the display code is just the part number.
    scheme = NumberingScheme(
        name="NoRevisionConfigured",
        pattern_segments=[
            {"kind": "literal", "value": "PART"},
            {"kind": "seq", "padding": 6, "base": 10, "auto_counter": True},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 6, "base": 10, "start_at": 1, "reset_policy": "never"},
        revision={},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": utc_now()},
    ).save()

    result, errors = allocate_number(
        scheme,
        {},
        create_part_if_missing=True,
        requested_revision_action="new_part",
        existing_part_number=None,
        user_email="user@example.com",
        cad_ref=None,
    )

    assert not errors
    assert result["revision"] == ""
    assert result["display_code"] == result["part_number"]
    part = Part.objects(part_number=result["part_number"]).first()
    assert part is not None
    assert (part.revision or "") == ""


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
            {"kind": "literal", "value": "CONC"},
            {"kind": "seq", "padding": 3, "base": 10},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 3, "base": 10, "start_at": 1, "reset_policy": "never"},
        revision={"policy": "alpha", "start": "A"},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": utc_now()},
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


def test_validate_rejects_field_segments():
    payload = {
        "name": "LegacyFieldScheme",
        "pattern_segments": [
            {"kind": "field", "field": "type", "casing": "upper"},
            {"kind": "seq", "padding": 3, "base": 10},
        ],
    }
    scheme, errors = normalize_scheme_payload(payload, "user@example.com", None)
    assert not errors
    v_errors, _, _ = validate_scheme_definition(scheme)
    assert any("must be literal, seq, or date" in error for error in v_errors)


def _simple_auto_scheme(name: str, padding: int = 3) -> NumberingScheme:
    return NumberingScheme(
        name=name,
        pattern_segments=[
            {"kind": "literal", "value": "GAP"},
            {"kind": "seq", "padding": padding, "base": 10, "start_at": 1, "auto_counter": True},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": padding, "base": 10, "start_at": 1, "reset_policy": "never"},
        revision={"policy": "none", "start": ""},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": utc_now()},
    ).save()


def _alloc(scheme, sequence_values=None):
    result, errors = allocate_number(
        scheme,
        {},
        create_part_if_missing=True,
        requested_revision_action="new_part",
        existing_part_number=None,
        user_email="user@example.com",
        cad_ref=None,
        sequence_values=sequence_values,
    )
    assert not errors, errors
    return result["part_number"]


def test_allocate_fills_gaps_after_manual_jump():
    # 1, 2, manual jump to 9 -> the next automatic allocations must fill 3..8, then 10.
    scheme = _simple_auto_scheme("GapFilling")

    assert _alloc(scheme) == "GAP-001"
    assert _alloc(scheme) == "GAP-002"
    assert _alloc(scheme, sequence_values=[9]) == "GAP-009"

    for expected in (3, 4, 5, 6, 7, 8):
        assert _alloc(scheme) == f"GAP-{expected:03d}"

    # 9 is taken, so the counter continues at 10.
    assert _alloc(scheme) == "GAP-010"


def test_allocate_never_reissues_a_number_even_after_part_deletion():
    scheme = _simple_auto_scheme("NoReuse")

    first = _alloc(scheme)
    assert first == "GAP-001"
    Part.objects(part_number=first).delete()

    # The value was claimed when issued; deleting the part must not free the number.
    assert _alloc(scheme) == "GAP-002"


def test_allocate_manual_value_respected_and_duplicates_rejected():
    scheme = _simple_auto_scheme("ManualStart")

    assert _alloc(scheme, sequence_values=[5]) == "GAP-005"
    # Requesting 5 again yields the next free value at or above 5.
    assert _alloc(scheme, sequence_values=[5]) == "GAP-006"


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
        audit={"created_at": utc_now()},
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
        audit={"created_at": utc_now()},
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


def test_allocate_manual_sequence_change_starts_independent_auto_series():
    scheme = NumberingScheme(
        name="ManualThenAuto",
        pattern_segments=[
            {"kind": "literal", "value": "PART"},
            {"kind": "seq", "padding": 3, "base": 10, "start_at": 1},
            {"kind": "seq", "padding": 3, "base": 10, "auto_counter": True},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 3, "base": 10, "start_at": 1, "reset_policy": "never"},
        revision={"policy": "alpha", "start": "A"},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": utc_now()},
    ).save()

    first, first_errors = allocate_number(
        scheme,
        {},
        create_part_if_missing=False,
        requested_revision_action="new_part",
        existing_part_number=None,
        user_email=None,
        cad_ref=None,
        sequence_values=[1, 1],
    )
    second, second_errors = allocate_number(
        scheme,
        {},
        create_part_if_missing=False,
        requested_revision_action="new_part",
        existing_part_number=None,
        user_email=None,
        cad_ref=None,
        sequence_values=[1, 1],
    )
    reset_series, reset_errors = allocate_number(
        scheme,
        {},
        create_part_if_missing=False,
        requested_revision_action="new_part",
        existing_part_number=None,
        user_email=None,
        cad_ref=None,
        sequence_values=[21, 1],
    )

    assert not first_errors
    assert not second_errors
    assert not reset_errors
    assert first["part_number"] == "PART-001-001"
    assert second["part_number"] == "PART-001-002"
    assert reset_series["part_number"] == "PART-021-001"
    assert first["counter_key"] != reset_series["counter_key"]


def test_allocate_skips_existing_part_numbers_within_manual_series():
    scheme = NumberingScheme(
        name="ManualSeriesSkipExisting",
        pattern_segments=[
            {"kind": "literal", "value": "PART"},
            {"kind": "seq", "padding": 3, "base": 10, "start_at": 1},
            {"kind": "seq", "padding": 3, "base": 10, "auto_counter": True},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 3, "base": 10, "start_at": 1, "reset_policy": "never"},
        revision={"policy": "alpha", "start": "A"},
        validation_rules={"max_length": 32, "allowed_charset": "A-Z0-9-", "require_seq_segment": True},
        audit={"created_at": utc_now()},
    ).save()
    Part(
        part_number="PART-021-001",
        revision="A",
        description="Existing",
        uom="EA",
        attrs={},
    ).save()

    result, errors = allocate_number(
        scheme,
        {},
        create_part_if_missing=False,
        requested_revision_action="new_part",
        existing_part_number=None,
        user_email=None,
        cad_ref=None,
        sequence_values=[21, 1],
    )

    assert not errors
    assert result["part_number"] == "PART-021-002"
    assert result["sequence_values_used"] == [21, 2]


def test_ensure_presets_seeds_simple_recommended_scheme():
    ensure_presets()

    scheme = NumberingScheme.objects(name="Default: PART-SEQ6").first()
    assert scheme is not None
    assert scheme.is_recommended is True
    assert NumberingScheme.objects(is_preset=True).count() == 1
    assert [segment.get("kind") for segment in scheme.pattern_segments] == ["literal", "seq"]
    assert scheme.pattern_segments[0].get("value") == "PART"
    assert scheme.pattern_segments[1].get("auto_counter") is True


def test_ensure_presets_seeds_no_revision_default():
    ensure_presets()

    scheme = NumberingScheme.objects(name="Default: PART-SEQ6").first()
    assert scheme is not None
    assert (scheme.revision or {}).get("policy") == "none"
    assert (scheme.revision or {}).get("start") == ""


def _forget_preset_seeding():
    """Simulate an instance upgraded from a build that had no seeding marker."""
    from app.services.app_settings import get_app_settings

    get_app_settings().update(set__numbering_preset_seeded=False)


def test_ensure_presets_migrates_seeded_alpha_revision_to_none():
    # The migration targets instances that predate the seeding marker, so the
    # preset is already in place and carries the revision "A" older seeds forced.
    ensure_presets()
    scheme = NumberingScheme.objects(name="Default: PART-SEQ6").first()
    scheme.update(set__revision={"policy": "alpha", "start": "A"})
    _forget_preset_seeding()

    ensure_presets()

    scheme.reload()
    assert (scheme.revision or {}).get("policy") == "none"
    assert (scheme.revision or {}).get("start") == ""


def test_ensure_presets_keeps_user_edits_to_default_scheme():
    ensure_presets()
    scheme = NumberingScheme.objects(name="Default: PART-SEQ6").first()
    # A deliberate (non-seeded) revision choice and a disable must survive restarts.
    scheme.update(set__revision={"policy": "numeric", "start": "01"}, set__is_active=False)

    ensure_presets()

    scheme.reload()
    assert (scheme.revision or {}).get("policy") == "numeric"
    assert scheme.is_active is False


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
        audit={"created_at": utc_now()},
    ).save()

    ensure_presets()

    recommended = list(NumberingScheme.objects(is_recommended=True))
    assert len(recommended) == 1
    assert recommended[0].name == "Existing Recommended"


def test_deleting_the_built_in_scheme_makes_it_stay_deleted():
    """Issue #98: it used to come back on the next restart, and the next.

    Seeding is a first-run convenience, not a promise that this scheme exists.
    """
    ensure_presets()
    NumberingScheme.objects(name="Default: PART-SEQ6").first().delete()

    ensure_presets()  # a restart
    ensure_presets()  # and another

    assert NumberingScheme.objects(name="Default: PART-SEQ6").first() is None
    assert NumberingScheme.objects.count() == 0


def test_upgrade_does_not_resurrect_a_scheme_deleted_before_the_marker_existed():
    """The instance in issue #98: deleted under the old build, then upgraded."""
    _simple_auto_scheme("House scheme")
    _forget_preset_seeding()

    ensure_presets()

    assert NumberingScheme.objects(name="Default: PART-SEQ6").first() is None
    assert [scheme.name for scheme in NumberingScheme.objects] == ["House scheme"]


def test_upgrade_keeps_seeding_into_an_instance_that_never_had_a_scheme():
    """An empty database is a first run whether or not the marker exists yet."""
    _forget_preset_seeding()

    ensure_presets()

    assert NumberingScheme.objects(name="Default: PART-SEQ6").first() is not None
