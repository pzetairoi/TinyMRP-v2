"""The root card in a Visual Summary must say what a child card says.

The root gets a wider box on the first row, and that box was drawn by its own
block rather than by the child cell routine. The block never resolved the
part's processes and never drew the approval icon, so the one part the pack is
actually about was the only one whose card showed neither its process colours
nor whether it was approved.

The bigger box is deliberate and stays. These tests pin the information.
"""

import io
import re

from pypdf import PdfReader
from reportlab.lib.units import mm

from app.models.bom import BOMLink
from app.models.part import Part
from app.services import docpacks as docpacks_service
from app.services.attrs import normalize_record_attrs
from app.services.docpacks import DocPackOptions, build_docpack


ROOT = "VS-ROOT-001"
CHILD = "VS-CHILD-002"

# Distinct primaries so a colour found in the page can only have come from the
# part that carries that process.
PROCESS_META = {
    "welding": {"color": "255,0,0"},
    "lasercut": {"color": "0,0,255"},
    "purchase": {"color": "0,255,0"},
}
ROOT_RGB = "1 0 0"      # welding, carried only by the root
CHILD_RGB = "0 0 1"     # lasercut, carried only by the child

# The root card sizes its icon against its larger QR; a child card uses 8mm.
ROOT_ICON_W = 11 * mm
CHILD_ICON_W = 8 * mm


def _approval_attrs(approved: bool) -> dict:
    """Approval is interpreted once, when the part is saved."""
    return normalize_record_attrs({"approved": "Approved" if approved else "pending"})


def _make_tree(root_processes, *, root_approved: bool) -> None:
    Part(part_number=ROOT, revision="1", description="ROOT ASSEMBLY",
         processes=list(root_processes),
         attrs=_approval_attrs(root_approved)).save()
    Part(part_number=CHILD, revision="1", description="CHILD PLATE",
         processes=["lasercut"], attrs=_approval_attrs(True)).save()
    BOMLink(parent_pn=ROOT, parent_rev="1", child_pn=CHILD, child_rev="1", qty=2).save()


def _visual_summary(app) -> bytes:
    app.config["PROCESS_META"] = PROCESS_META
    _name, data, mime = build_docpack(
        DocPackOptions(
            root_pn=ROOT,
            root_rev="1",
            depth="full",
            want_visual_list=True,
            want_selected_files=False,
        )
    )
    assert mime == "application/pdf"
    return data


def _stroke_colours(data: bytes) -> set:
    reader = PdfReader(io.BytesIO(data))
    raw = reader.pages[0].get_contents().get_data().decode("latin-1")
    return set(re.findall(r"([\d.]+ [\d.]+ [\d.]+) RG", raw))


class _IconSpy:
    """Records every icon the visual summary draws, with its box width."""

    def __init__(self, real):
        self._real = real
        self.calls = []

    def __call__(self, c, x, y, w, h, svg_name, png_fallback):
        self.calls.append({"name": svg_name, "x": x, "y": y, "w": w, "h": h})
        return self._real(c, x, y, w, h, svg_name, png_fallback)

    def widths_for(self, svg_name: str):
        return [call["w"] for call in self.calls if call["name"] == svg_name]


def _spy_on_icons(monkeypatch) -> _IconSpy:
    spy = _IconSpy(docpacks_service._draw_svg_or_png)
    monkeypatch.setattr(docpacks_service, "_draw_svg_or_png", spy)
    return spy


def test_root_card_is_ringed_in_its_own_process_colour(app):
    """The root carries welding; nothing else in the pack does."""

    with app.app_context():
        _make_tree(["welding"], root_approved=False)
        colours = _stroke_colours(_visual_summary(app))

    assert ROOT_RGB in colours, (
        "the root's process colour is absent, so its box is not colour-coded"
    )
    assert CHILD_RGB in colours, "the child's process colour regressed"


def test_root_card_shows_the_not_approved_icon(app, monkeypatch):
    with app.app_context():
        spy = _spy_on_icons(monkeypatch)
        _make_tree(["welding"], root_approved=False)
        _visual_summary(app)

    widths = spy.widths_for("notapproved.svg")
    assert any(abs(w - ROOT_ICON_W) < 0.01 for w in widths), (
        "no not-approved icon was drawn on the root card"
    )
    assert any(abs(w - CHILD_ICON_W) < 0.01 for w in spy.widths_for("approved.svg")), (
        "the child card's approval icon regressed"
    )


def test_root_card_shows_the_approved_icon_when_the_root_is_approved(app, monkeypatch):
    with app.app_context():
        spy = _spy_on_icons(monkeypatch)
        _make_tree(["welding"], root_approved=True)
        _visual_summary(app)

    assert any(abs(w - ROOT_ICON_W) < 0.01 for w in spy.widths_for("approved.svg")), (
        "an approved root is not shown as approved on its own card"
    )
    assert not any(
        abs(w - ROOT_ICON_W) < 0.01 for w in spy.widths_for("notapproved.svg")
    ), "an approved root was also stamped not approved"


def test_a_bought_root_is_not_stamped_not_approved(app, monkeypatch):
    """The child cells never stamp hardware/purchased parts; the root matches."""

    with app.app_context():
        spy = _spy_on_icons(monkeypatch)
        _make_tree(["purchase"], root_approved=False)
        _visual_summary(app)

    assert not any(
        abs(w - ROOT_ICON_W) < 0.01 for w in spy.widths_for("notapproved.svg")
    ), "a purchased root was stamped not approved, which no child card would do"


def test_a_synthetic_root_carries_no_approval_stamp(app, monkeypatch):
    """The compile-sheet flow labels the card with a root that is not a part.

    There is no approval state to report for a label, so stamping it "not
    approved" would invent one.
    """
    from app.services.docpacks import _visual_list_pdf

    with app.app_context():
        app.config["PROCESS_META"] = PROCESS_META
        spy = _spy_on_icons(monkeypatch)
        Part(part_number=CHILD, revision="1", description="CHILD PLATE",
             processes=["lasercut"], attrs=_approval_attrs(True)).save()
        assert _visual_list_pdf(
            [(CHILD, "1", 1.0)], root_pn="NOT-A-REAL-PART", root_rev="1"
        )

    for name in ("approved.svg", "notapproved.svg"):
        assert not any(abs(w - ROOT_ICON_W) < 0.01 for w in spy.widths_for(name)), (
            f"a synthetic root was stamped with {name}"
        )
