from types import SimpleNamespace

from app.services.docpacks import _visual_list_pdf


def test_visual_list_uses_merged_approved_fields(app, monkeypatch, tmp_path):
    calls = []

    fake_part = SimpleNamespace(
        part_number="VIS-101",
        revision="A",
        description="Visual Part",
        attrs={},
        props={"approvedby": "QA"},
        processes=[],
    )

    def fake_part_by(pn, rev):
        if pn == "VIS-101":
            return fake_part
        return None

    def fake_draw(*args):
        calls.append(args[-2])

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        monkeypatch.setattr("app.services.docpacks._part_by", fake_part_by)
        monkeypatch.setattr("app.services.docpacks._draw_svg_or_png", fake_draw)
        pdf = _visual_list_pdf([("VIS-101", "A", 1.0)], root_pn="ROOT-100", root_rev="A")

    assert pdf
    assert "approved.svg" in calls


def test_visual_list_treats_approved_status_value_as_approved(app, monkeypatch, tmp_path):
    calls = []

    fake_part = SimpleNamespace(
        part_number="VIS-102",
        revision="A",
        description="Visual Part",
        attrs={"approved": "Approved"},
        props={},
        processes=[],
    )

    def fake_part_by(pn, rev):
        if pn == "VIS-102":
            return fake_part
        return None

    def fake_draw(*args):
        calls.append(args[-2])

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        monkeypatch.setattr("app.services.docpacks._part_by", fake_part_by)
        monkeypatch.setattr("app.services.docpacks._draw_svg_or_png", fake_draw)
        pdf = _visual_list_pdf([("VIS-102", "A", 1.0)], root_pn="ROOT-100", root_rev="A")

    assert pdf
    assert "approved.svg" in calls
    assert "notapproved.svg" not in calls
