"""exact_bom_pairs batches by level. Prove it still authorises exactly.

The walk used to issue one BOMLink query per part visited - 1348 inside a
single doc-pack options call. Batching asks for a whole level at once, which
means the query returns links for EVERY revision of those part numbers, not
just the pair being expanded.

That set is the authorisation boundary for an export, so the risk is not
slowness, it is authorising a part that was never in this tree. These tests
exist for that, not for the speedup.
"""

from __future__ import annotations

import pytest

from app.models.bom import BOMLink
from app.models.part import Part
from app.services.export_security import ExportSecurityError, exact_bom_pairs


@pytest.fixture
def tree(app):
    with app.app_context():
        BOMLink.objects.delete()
        Part.objects.delete()
        # Two revisions of the same parent with DIFFERENT children. A batched
        # query sees both; only the requested revision may contribute.
        BOMLink(parent_pn="ASM", parent_rev="1", child_pn="ONLY-IN-REV1", child_rev="").save()
        BOMLink(parent_pn="ASM", parent_rev="2", child_pn="ONLY-IN-REV2", child_rev="").save()
        BOMLink(parent_pn="ONLY-IN-REV1", parent_rev="", child_pn="DEEP", child_rev="").save()
        yield


def test_a_sibling_revision_is_not_pulled_in(app, tree):
    with app.app_context():
        pairs = exact_bom_pairs("ASM", "1", full=True)

    names = {pn for pn, _rev in pairs}
    assert "ONLY-IN-REV1" in names
    assert "ONLY-IN-REV2" not in names, (
        "the batched query returned another revision's children and they were authorised"
    )


def test_it_still_descends_past_the_first_level(app, tree):
    with app.app_context():
        pairs = exact_bom_pairs("ASM", "1", full=True)
    assert "DEEP" in {pn for pn, _rev in pairs}, "level batching stopped descending"


def test_top_level_only_does_not_descend(app, tree):
    with app.app_context():
        pairs = exact_bom_pairs("ASM", "1", full=False)
    names = {pn for pn, _rev in pairs}
    assert "ONLY-IN-REV1" in names
    assert "DEEP" not in names


def test_the_root_is_always_included(app, tree):
    with app.app_context():
        pairs = exact_bom_pairs("ASM", "1", full=True)
    assert ("ASM", "1") in pairs


def test_a_cycle_terminates(app):
    """A part that lists itself as a descendant must not loop forever."""
    with app.app_context():
        BOMLink.objects.delete()
        BOMLink(parent_pn="A", parent_rev="", child_pn="B", child_rev="").save()
        BOMLink(parent_pn="B", parent_rev="", child_pn="A", child_rev="").save()
        pairs = exact_bom_pairs("A", "", full=True)
    assert {pn for pn, _rev in pairs} == {"A", "B"}


def test_a_blank_part_number_is_refused(app):
    with app.app_context():
        with pytest.raises(ExportSecurityError):
            exact_bom_pairs("", "", full=True)


def test_preflight_still_refuses_an_unauthorised_pair_set(app, monkeypatch):
    """The pair-level gate is what the per-file check was leaning on."""
    from app.services import export_security

    monkeypatch.setattr(export_security, "require_export_permissions", lambda *a, **k: None)
    monkeypatch.setattr(export_security, "authorised_part_pairs", lambda user, pairs: frozenset())

    with app.app_context():
        with pytest.raises(export_security.ExportSecurityError):
            export_security.preflight_export_plan(
                object(), [("ASM", "1")], require_bom=False, include_files=True
            )


def test_file_lookup_matches_part_numbers_case_insensitively(app):
    """_files_for_pairs batches with $in, which is case-SENSITIVE by default.

    Swapping the per-pair __iexact query for a plain $in silently dropped files
    whose stored part_number differed only in case. In the test suite that hid
    a path-traversal record from the safety check and turned a 403 into a 200 -
    a performance change quietly disabling a security check, which is the worst
    way for one to fail.
    """
    from app.models.artifact import PartFile
    from app.services.export_security import _files_for_pairs

    with app.app_context():
        PartFile.objects.delete()
        PartFile(
            part_number="aws-z-009025",
            revision="",
            ext="pdf",
            ext_group="pdf",
            rel_path="pdf/x.pdf",
            path="/data/deliverables/pdf/x.pdf",
        ).save()

        found = _files_for_pairs([("AWS-Z-009025", "")], None)

    assert len(found) == 1, "a differently-cased part number was dropped by the batch"
