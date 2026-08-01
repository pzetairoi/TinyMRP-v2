"""The visual-list stamp reflects the part's stored approval boolean.

Aliases and status strings are still honoured, but they are interpreted once
when the part is saved rather than re-derived while rendering the PDF, so the
stamp can never disagree with the badge or the filters.
"""

from app.models.part import Part
from app.services.attrs import normalize_record_attrs
from app.services.docpacks import _visual_list_pdf


def _stamps_for(app, monkeypatch, tmp_path, pn: str, attrs: dict) -> list[str]:
    calls: list[str] = []

    def fake_draw(*args):
        calls.append(args[-2])

    with app.app_context():
        Part(
            part_number=pn,
            revision="A",
            description="Visual Part",
            attrs=normalize_record_attrs(attrs),
        ).save()
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        monkeypatch.setattr("app.services.docpacks._draw_svg_or_png", fake_draw)
        pdf = _visual_list_pdf([(pn, "A", 1.0)], root_pn="ROOT-100", root_rev="A")

    assert pdf
    return calls


def test_visual_list_stamps_an_approver_identity_as_approved(app, monkeypatch, tmp_path):
    calls = _stamps_for(app, monkeypatch, tmp_path, "VIS-101", {"approvedby": "QA"})

    assert "approved.svg" in calls
    assert "notapproved.svg" not in calls


def test_visual_list_treats_approved_status_value_as_approved(app, monkeypatch, tmp_path):
    calls = _stamps_for(app, monkeypatch, tmp_path, "VIS-102", {"approved": "Approved"})

    assert "approved.svg" in calls
    assert "notapproved.svg" not in calls


def test_visual_list_stamps_an_unapproved_part_as_not_approved(app, monkeypatch, tmp_path):
    calls = _stamps_for(app, monkeypatch, tmp_path, "VIS-103", {"approved": "pending"})

    assert "notapproved.svg" in calls
    assert "approved.svg" not in calls
