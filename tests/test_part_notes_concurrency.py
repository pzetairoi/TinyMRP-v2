"""Concurrent note edits (E9, Phase 8).

Notes are the only place a browser user types prose that another browser user
can silently overwrite. Comments are append-only and status/priority are
single-field toggles, so this is the one path where a lost update actually
costs somebody their work.
"""

from __future__ import annotations


def test_concurrent_note_edits_warn_and_return_what_was_replaced():
    """E9. Notes are the one place a browser user can silently lose prose.

    Comments are append-only and status/priority are single-field toggles, so
    notes is where a lost update actually costs someone their work. The owner
    chose warn-and-save over reject: rejecting would discard the text the user
    just typed, which is the same harm from the other direction.

    The replaced text must come back. A warning that says "you overwrote
    someone" without handing back what was lost is barely better than silence.
    """
    from app.models.part import Part
    from app.services.part_annotations import set_part_notes

    part = Part(part_number="CONC-1", revision="A").save()

    first = set_part_notes(part, "written by Ana")
    loaded_at = first["notes_updated_at"]
    assert loaded_at, "the client needs a baseline to detect a conflict with"

    # Someone else saves in between, so the stored copy moves on.
    set_part_notes(part, "written by Bruno")

    result = set_part_notes(part, "written by Ana, second attempt", base_updated_at=loaded_at)

    assert result.get("conflict") is True
    assert result["replaced_notes"] == "written by Bruno"
    # Save still went through - warn, do not reject.
    assert result["notes"] == "written by Ana, second attempt"

    # No baseline, or a current one, must NOT cry conflict.
    fresh = set_part_notes(part, "third", base_updated_at=result["notes_updated_at"])
    assert not fresh.get("conflict")
    assert not set_part_notes(part, "fourth").get("conflict")
    assert not set_part_notes(part, "fifth", base_updated_at="not-a-timestamp").get("conflict")
