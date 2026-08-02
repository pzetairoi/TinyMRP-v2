"""Only FLATBOM/TREEBOM rows create parts; files never do.

CAD exports routinely carry temp artefacts whose names parse into a bogus
revision (``PN_REV__<guid>.tmp - OTHER.STL``). Accepting those invented a
part/revision pair, which then polluted the revision family behind where-used
and BOM navigation.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from app.services.upload_pack import _policy_options, parse_import_package

FLATBOM = (
    "{'partnumber':'ROOT-1','description':'Root assembly','revision':''}\n"
    "{'partnumber':'CHILD-1','description':'A child','revision':''}\n"
)
TREEBOM = (
    "ITEM NO.\tPART NUMBER\tREVISION\tQTY\n"
    "1\tROOT-1\t\t1\n"
    "1.1\tCHILD-1\t\t2\n"
)


def _pack(extra_files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("bom/P_REV__FLATBOM.txt", FLATBOM)
        archive.writestr("bom/P_REV__TREEBOM.txt", TREEBOM)
        for name, payload in extra_files.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def _parse(app, extra_files):
    with app.app_context():
        return parse_import_package(_pack(extra_files), "pack.zip", _policy_options())


def test_only_bom_rows_create_parts(app):
    parsed = _parse(app, {"deliverables/step/ROOT-1_REV_.step": b"x"})

    assert set(parsed["parts"]) == {("ROOT-1", ""), ("CHILD-1", "")}


def test_a_temp_artefact_never_invents_a_part(app):
    """The exact shape SolidWorks emits alongside a real STL export."""

    orphan = "deliverables/stl/ROOT-1_REV__208f9c535ce14cacb33afc90bcd6af58.tmp - CHILD-1-1.STL"
    parsed = _parse(app, {orphan: b"x", "deliverables/stl/ROOT-1_REV_.stl": b"y"})

    # No invented revision, and the legitimate sibling still lands.
    assert set(parsed["parts"]) == {("ROOT-1", ""), ("CHILD-1", "")}
    assert [file["pair"] for file in parsed["files"]] == [("ROOT-1", "")]
    assert not [pair for pair in parsed["parts"] if ".tmp" in pair[1]]


def test_the_user_is_warned_about_a_skipped_file(app):
    orphan = "deliverables/stl/ROOT-1_REV__abc.tmp - CHILD-1-1.STL"
    parsed = _parse(app, {orphan: b"x"})

    warnings = [
        warning
        for warning in parsed["diagnostics"]["warnings"]
        if warning["stage"] == "files.orphan"
    ]

    assert len(warnings) == 1
    # The message must name the file so the user can act on it.
    assert "ROOT-1_REV__abc.tmp - CHILD-1-1.STL" in warnings[0]["message"]


@pytest.mark.parametrize(
    "entry",
    [
        "deliverables/step/UNKNOWN-9_REV_.step",
        "extra/UNKNOWN-9/notes.txt",
    ],
)
def test_a_file_for_an_undeclared_part_is_skipped(app, entry):
    """Applies to associated files as much as managed deliverables."""

    parsed = _parse(app, {entry: b"x"})

    assert ("UNKNOWN-9", "") not in parsed["parts"]
    assert parsed["files"] == []
    assert any(
        warning["stage"] == "files.orphan"
        for warning in parsed["diagnostics"]["warnings"]
    )


def test_files_for_declared_parts_are_still_accepted(app):
    """The guard must not reject legitimate deliverables."""

    parsed = _parse(
        app,
        {
            "deliverables/step/ROOT-1_REV_.step": b"a",
            "deliverables/png/CHILD-1_REV_.png": b"b",
            "deliverables/png/ROOT-1_REV__DWG.png": b"c",
        },
    )

    assert sorted(file["pair"] for file in parsed["files"]) == [
        ("CHILD-1", ""),
        ("ROOT-1", ""),
        ("ROOT-1", ""),
    ]
    assert not [
        warning
        for warning in parsed["diagnostics"]["warnings"]
        if warning["stage"] == "files.orphan"
    ]


def _plan(app, **modes):
    from app.services.field_config import get_field_config
    from app.services.upload_pack import build_import_plan, load_import_state

    with app.app_context():
        options = _policy_options(**modes)
        parsed = parse_import_package(
            _pack({"deliverables/step/ROOT-1_REV_.step": b"x"}), "pack.zip", options
        )
        return build_import_plan(
            parsed, load_import_state(parsed), options, get_field_config()
        )


def _actions(entry, key):
    return {row["action"] for row in entry[key]}


def test_skipping_every_policy_changes_nothing_even_for_new_parts(app):
    """"Skip" must mean skip on a new part too, not just an existing one."""

    plan = _plan(app, data_mode="skip", bom_mode="skip", file_mode="skip")

    assert plan["parts"], "expected the BOM to still be planned"
    for entry in plan["parts"]:
        assert entry["changed"] is False, entry["part_number"]
        assert _actions(entry, "properties") <= {"skipped", "unchanged"}
        assert _actions(entry, "approval") <= {"skipped", "unchanged"}


def test_each_policy_acts_only_on_its_own_domain(app):
    """Selecting properties alone must not write BOM rows or files."""

    plan = _plan(app, data_mode="replace_all", bom_mode="skip", file_mode="skip")

    for entry in plan["parts"]:
        assert entry["bom"]["action"] in {"skip", "skipped", "unchanged", "none", ""}
        assert _actions(entry, "files") <= {"skipped", "unchanged"}
    # Properties themselves still apply.
    assert any(_actions(entry, "properties") & {"add", "replace"} for entry in plan["parts"])


def _png_bytes() -> bytes:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (400, 300), (10, 120, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_preview_carries_the_root_image_without_storing_anything(app, tmp_path):
    """The user sees what is being imported before anything is written."""

    from app.models.artifact import PartFile
    from app.services.upload_pack import import_upload_pack

    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    pack = _pack({"deliverables/png/ROOT-1_REV_.png": _png_bytes()})

    with app.app_context():
        result = import_upload_pack(
            pack, "pack.zip", uploaded_by="t@example.com", dry_run=True
        )

        assert result["root"] == "ROOT-1"
        assert result["root_preview"].startswith("data:image/png;base64,")
        # Preview-only: nothing reaches storage or the file records.
        assert list(tmp_path.iterdir()) == []
        assert PartFile.objects.count() == 0


def test_a_pack_without_a_root_image_reports_no_preview(app, tmp_path):
    from app.services.upload_pack import import_upload_pack

    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)

    with app.app_context():
        result = import_upload_pack(
            _pack({}), "pack.zip", uploaded_by="t@example.com", dry_run=True
        )

        assert result["root_preview"] == ""


def test_a_drawing_png_is_not_used_as_the_part_preview(app, tmp_path):
    """_DWG images are drawings, not the part thumbnail."""

    from app.services.upload_pack import import_upload_pack

    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    pack = _pack({"deliverables/png/ROOT-1_REV__DWG.png": _png_bytes()})

    with app.app_context():
        result = import_upload_pack(
            pack, "pack.zip", uploaded_by="t@example.com", dry_run=True
        )

        assert result["root_preview"] == ""
