"""The published help is the spec for sharing; this holds the code to it.

Every claim below is a sentence a user can read in the in-app help and act on.
Three rounds of fixes moved what a link exposes, and each round the help was
edited by hand alongside the code - which is exactly the arrangement that
drifts. These tests read the help file itself, so a level renamed in one place
and not the other fails here rather than in front of a customer.
"""

import re
from pathlib import Path

import pytest

from app.models.artifact import PartFile
from app.models.part import Part
from app.views.part_shares import SHARE_ACCESS_TIERS, _SHARE_TIER_ALIASES


HELP = Path(__file__).resolve().parents[1] / "docs" / "help" / "01_web_ui_walkthrough.md"
PAGE = Path(__file__).resolve().parents[1] / "frontend" / "src" / "pages" / "PartDetailPage.tsx"


def _help_text() -> str:
    body = HELP.read_text(encoding="utf-8")
    start = body.index("### Sharing a part outside the system")
    return body[start : body.index("## Doc Packs", start)]


def test_help_documents_exactly_the_levels_that_exist():
    """A level named in the help must be one the API actually accepts."""

    text = _help_text()
    documented = {
        row.strip().lower()
        for row in re.findall(r"^\|\s*\*\*(.+?)\*\*\s*\|", text, re.MULTILINE)
    }
    # "Full access" is the label; "full" is the wire value behind it.
    assert documented == {"preview", "review", "full access"}
    assert set(SHARE_ACCESS_TIERS) == {"preview", "review", "full"}
    assert _SHARE_TIER_ALIASES == {"supplier": "full"}


def test_help_switch_list_matches_the_grants_the_api_takes():
    """Each bullet under Customise must name a grant the server honours."""

    bullets = {
        name.strip().lower()
        for name in re.findall(r"^- \*\*(.+?)\*\*", _help_text(), re.MULTILINE)
    }
    assert bullets == {
        "drawings",
        "neutral cad",
        "datasheets",
        "all files",
        "attributes",
        "doc packs",
    }
    grants = set(SHARE_ACCESS_TIERS["full"])
    assert grants == {
        "allow_drawings",
        "allow_neutral_cad",
        "allow_datasheets",
        "allow_all_files",
        "allow_attributes",
        "allow_docpacks",
    }
    # Every switch is on at Full access and off at Preview - that is what makes
    # the two ends of the table meaningful.
    assert all(SHARE_ACCESS_TIERS["full"][name] for name in grants)
    assert not any(SHARE_ACCESS_TIERS["preview"][name] for name in grants)


def test_the_share_form_offers_what_the_help_describes():
    """The levels and switches the page renders, against the same help text."""

    source = PAGE.read_text(encoding="utf-8")
    tiers = re.search(
        r"const SHARE_TIERS: Record<ShareTier.*?\n\};", source, re.DOTALL
    ).group(0)
    assert set(re.findall(r"^  (\w+): \{$", tiers, re.MULTILINE)) == set(
        SHARE_ACCESS_TIERS
    )
    assert 'label: "Full access"' in tiers
    assert "Supplier" not in tiers

    labels = re.search(
        r"const SHARE_GRANT_LABELS.*?\n\];", source, re.DOTALL
    ).group(0)
    assert set(re.findall(r'key: "(\w+)"', labels)) == set(SHARE_ACCESS_TIERS["full"])


@pytest.fixture
def shared_part(client, app, tmp_path):
    from tests.test_part_share_surface import _admin, _assembly, ROOT, REV

    _admin(client, "help-contract@example.com")
    _assembly(app, tmp_path)
    return ROOT, REV


def _share(client, root, rev, **payload):
    resp = client.post(
        f"/api/parts/{root}/shares",
        json={"rev": rev, "expires_in_days": 30, **payload},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()


def test_help_claim_no_permission_notice_ever_appears_on_a_share(
    client, app, shared_part
):
    """"a shared link has no account, so no permission notice ever appears".

    The page hides the Doc Packs form and shows a missing-permission notice
    unless can_export / can_bom_read / can_files_read say otherwise. A share
    has no account to carry those, so the grants have to answer for them.
    """
    root, rev = shared_part
    created = _share(client, root, rev, tier="full", allow_children=True)
    public = app.test_client()
    detail = public.get(
        f"/api/share/part/{created['share_id']}/{created['share_token']}"
        f"/part_detail?pn={root}&rev={rev}"
    ).get_json()
    assert detail["can_files_read"] is True
    assert detail["can_bom_read"] is True
    assert detail["can_export"] is True


def test_help_claim_markups_and_comments_are_never_exposed(client, app, shared_part):
    """"Review markups and internal comments are never exposed on a shared link"."""

    root, rev = shared_part
    created = _share(client, root, rev, tier="full", allow_children=True)
    public = app.test_client()
    base = f"/api/share/part/{created['share_id']}/{created['share_token']}"
    detail = public.get(f"{base}/part_detail?pn={root}&rev={rev}").get_json()

    assert detail["comments"] == []
    assert detail["part"]["notes"] == ""
    assert detail["part"]["field_values"]["notes"] == ""
    assert detail["part"]["field_values"]["comments"] == ""
    assert not any("markup" in key for key in detail)
    # The approver's identity is a person's name, not part data.
    assert detail["part"]["field_values"]["approved_by"] == ""
    assert detail["approver_profile"] is None
    assert detail["uploader_profile"] is None


def test_help_claim_internal_files_are_withheld_at_every_level(
    client, app, shared_part
):
    """"never shared, at any level" - including the widest one."""

    root, rev = shared_part
    created = _share(client, root, rev, tier="full", allow_children=True)
    public = app.test_client()
    rows = public.get(
        f"/api/share/part/{created['share_id']}/{created['share_token']}"
        f"/files_overview?pn={root}&rev={rev}"
    ).get_json()["current_revision"]["files"]
    names = [row["name"] for row in rows]
    assert "costing.xlsx" in names
    assert "margins.xlsx" not in names, "source=internal is withheld at Full access too"


def test_help_claim_a_pack_can_only_hold_what_the_link_grants(
    client, app, shared_part
):
    """"A pack can only ever contain file types the same link already grants"."""

    root, rev = shared_part
    created = _share(client, root, rev, tier="review", allow_docpacks=True)
    public = app.test_client()
    base = f"/api/share/part/{created['share_id']}/{created['share_token']}"
    offered = public.get(
        f"{base}/docpacks/options?pn={root}&rev={rev}&depth=top"
    ).get_json()["file_types"]
    assert "step" not in offered and "dxf" not in offered
    assert "pdf" in offered and "datasheet" in offered

    refused = public.post(
        f"{base}/docpacks/build",
        json={
            "pn": root,
            "rev": rev,
            "depth": "top",
            "file_types": ["step"],
            "selected_files": True,
        },
    )
    assert refused.status_code == 400


def test_help_claim_a_granted_pack_actually_builds(client, app, shared_part):
    """"lets the recipient build a document pack" - the whole point of it.

    The tab used to open onto a permission notice instead of the form, so the
    grant was real and the pack was still unreachable. This posts what the
    form posts and insists on a zip with files in it.
    """
    import io
    import zipfile

    root, rev = shared_part
    created = _share(client, root, rev, tier="full", allow_children=True)
    public = app.test_client()
    built = public.post(
        f"/api/share/part/{created['share_id']}/{created['share_token']}"
        "/docpacks/build",
        json={
            "pn": root,
            "rev": rev,
            "depth": "full",
            "include_consumed": False,
            "classified": "show",
            "process_mode": "all",
            "processes": [],
            "file_types": ["pdf", "step"],
            "selected_files": True,
            "excel_bom": True,
            "excel_all_fields": False,
            "excel_field_ids": ["part_number", "revision", "description", "qty"],
            "pdf_binder": False,
            "whereused_report": False,
            "markup_files": False,
            "markup_report": False,
            "binder_add_whereused": False,
            "binder_add_markups": False,
        },
    )
    assert built.status_code == 200, built.get_data(as_text=True)
    names = zipfile.ZipFile(io.BytesIO(built.data)).namelist()
    assert any(name.endswith(".pdf") for name in names)
    assert any(name.endswith(".step") for name in names)
    assert any(name.endswith(".xlsx") for name in names)
    assert not any("markup" in name.lower() for name in names)


def test_help_claim_the_floor_survives_a_part_with_nothing_else(
    client, app, tmp_path
):
    """"a link that shows nothing would not be worth sending".

    A part carrying only a preview PNG still has to render one at Preview.
    """
    from tests.test_part_share_surface import _admin

    _admin(client, "help-floor@example.com")
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILE_SOURCES"] = [{"local_root": str(tmp_path)}]
    Part(part_number="HELP-BARE", revision="A", description="bare").save()
    rel = "png/HELP-BARE.png"
    abs_path = tmp_path / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(b"png")
    PartFile(
        part_number="HELP-BARE",
        revision="A",
        ext_group="png",
        ext="png",
        is_dwg=False,
        rel_path=rel,
        path=str(abs_path),
    ).save()

    created = _share(client, "HELP-BARE", "A", tier="preview")
    public = app.test_client()
    detail = public.get(
        f"/api/share/part/{created['share_id']}/{created['share_token']}"
        "/part_detail?pn=HELP-BARE&rev=A"
    ).get_json()
    assert detail["images"], "the floor must hold even when nothing else exists"
