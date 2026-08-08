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


def test_preresolved_parts_do_not_weaken_the_file_check(app):
    """The map makes the check cheap. It must not make it permissive.

    exact_file_part ran a Part query per file record - about 5592 against 1372
    files on a large assembly. Callers can now hand in parts they already
    resolved through scope_queryset, turning it into a dict lookup.

    The property that matters: a file whose part is ABSENT from that scoped map
    is still refused, exactly as the query refused a part outside scope. An
    earlier attempt deleted this check on the argument that it could not fail;
    it could, and a path-traversal test caught it.
    """
    from app.services.file_security import exact_file_part

    class _User:
        is_authenticated = True

    with app.app_context():
        # Empty map: nothing is in scope, so nothing may be read.
        assert exact_file_part(_User(), "ASM", "1", parts_in_scope={}) is None
        # A different part in scope does not authorise this one.
        assert (
            exact_file_part(_User(), "ASM", "1", parts_in_scope={("other", ""): object()})
            is None
        )


def test_flatten_bom_still_accumulates_quantities_across_shared_paths(app):
    """The children memo must not change the arithmetic.

    _flatten_bom deliberately has NO visited set: a shared subassembly appears
    on several paths and its quantities must add up. Memoising the link fetch
    shares the query, not the traversal - so a part reached twice must still be
    counted twice.

    This is the assertion that matters. A wrong quantity on a document pack is
    a manufacturing error, not a slow page.
    """
    from app.services.docpacks import _flatten_bom

    with app.app_context():
        BOMLink.objects.delete()
        # TOP uses SHARED twice, via two different intermediates, 2 x 3 and 5 x 3.
        BOMLink(parent_pn="TOP", parent_rev="", child_pn="MID-A", child_rev="", qty=2).save()
        BOMLink(parent_pn="TOP", parent_rev="", child_pn="MID-B", child_rev="", qty=5).save()
        BOMLink(parent_pn="MID-A", parent_rev="", child_pn="SHARED", child_rev="", qty=3).save()
        BOMLink(parent_pn="MID-B", parent_rev="", child_pn="SHARED", child_rev="", qty=3).save()

        rows = {(pn, rev): qty for pn, rev, qty in _flatten_bom("TOP", "", full=True)}

    assert rows[("MID-A", "")] == 2
    assert rows[("MID-B", "")] == 5
    # 2x3 via MID-A plus 5x3 via MID-B. The memo shares the LINK LOOKUP for
    # SHARED; it must not collapse the two paths into one.
    assert rows[("SHARED", "")] == 21, f"quantities collapsed: got {rows.get(('SHARED', ''))}"
