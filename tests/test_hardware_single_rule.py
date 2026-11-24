"""One rule decides what is hardware, and every list that sets hardware apart asks it.

A part is hardware when a process names it hardware or fasteners, or when its
file sits in a hardware folder. Category plays no part. The visual summary
leaves out exactly what the hardware summary lists, standalone and in a binder.

The reported failure: a fastener whose process read "hardware" but whose
category read "Fastener" was drawn on the visual summary and missing from the
hardware summary, because a category without the word "hardware" vetoed the
process. A part in a hardware folder fell through the same way whenever its
stored process predated the folder rule or the folder setting.
"""

import csv
import io
import os
import re
import zipfile

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.models.artifact import PartFile
from app.models.auth import Role, User
from app.models.bom import BOMLink
from app.models.part import Part
from app.services.docpacks import DocPackOptions, build_docpack
from app.services.insights import classify_part, is_hardware
from app.services.permissions import PERMISSION_REGISTRY
from app.services.processmeta import load_process_meta


ROOT = "HR-100"
MACHINED = "HR-200"
BY_CATEGORY = "HR-301"   # hardware process, category "Fastener": the report
BY_TOOLBOX = "HR-302"    # Toolbox folder, stored process still "purchase"
BY_SETTING = "HR-303"    # folder an admin only later named a hardware folder
HARDWARE = (BY_CATEGORY, BY_TOOLBOX, BY_SETTING)
HW_PAGE_MARK = "Hardware Summary Details"


def _write_pdf(path: str, label: str) -> None:
    c = canvas.Canvas(path)
    c.drawString(100, 750, label)
    c.showPage()
    c.save()


def _drawing(file_root: str, pn: str, rev: str) -> None:
    pdf_path = os.path.join(file_root, f"{pn}.pdf")
    _write_pdf(pdf_path, f"{pn} DRAWING")
    PartFile(part_number=pn, revision=rev, ext_group="pdf", ext="pdf", rel_path=f"{pn}.pdf", path=pdf_path).save()


def _build_assembly(app, file_root: str) -> None:
    Part(part_number=ROOT, revision="1", description="FRAME ASSEMBLY", processes=["assembly"]).save()
    Part(part_number=MACHINED, revision="1", description="MACHINED BLOCK", processes=["machine"]).save()
    Part(part_number=BY_CATEGORY, revision="", description="HEX BOLT M8", processes=["hardware"],
         category="Fastener").save()
    # Saved without the resolver, as a record stored before the folder rule
    # existed is: its process still reads what the Toolbox file said.
    Part(part_number=BY_TOOLBOX, revision="", description="WASHER M8", processes=["purchase"],
         attrs={"folder": r"C:\SOLIDWORKS Data\Toolbox\ansi metric\washers"}).save(sync_materialized=False)
    Part(part_number=BY_SETTING, revision="", description="NUT M8",
         attrs={"process": "Purchase", "folder": r"D:\Library\Bolts"}).save()
    for child, qty in ((MACHINED, 2), (BY_CATEGORY, 4), (BY_TOOLBOX, 8), (BY_SETTING, 4)):
        rev = "1" if child == MACHINED else ""
        BOMLink(parent_pn=ROOT, parent_rev="1", child_pn=child, child_rev=rev, qty=qty).save()
    _drawing(file_root, ROOT, "1")
    _drawing(file_root, MACHINED, "1")
    # The admin names "bolts" a hardware folder after the nut was stored, and
    # does not ask for existing parts to be recomputed.
    app.config["HARDWARE_FOLDERS"] = list(app.config.get("HARDWARE_FOLDERS") or []) + ["bolts"]


def _opts(**kwargs) -> DocPackOptions:
    base = dict(root_pn=ROOT, root_rev="1", depth="full", file_types=["pdf"], want_selected_files=False)
    base.update(kwargs)
    return DocPackOptions(**base)


def _pages(data: bytes) -> list:
    return [page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages]


def _assert_partitioned(pages: list) -> None:
    hardware_pages = [text for text in pages if HW_PAGE_MARK in text]
    other_pages = [text for text in pages if HW_PAGE_MARK not in text]
    assert hardware_pages, "the hardware summary is missing"
    for pn in HARDWARE:
        assert any(pn in text for text in hardware_pages), f"{pn} is missing from the hardware summary"
        assert not any(pn in text for text in other_pages), f"{pn} is drawn outside the hardware summary"
    assert any(MACHINED in text for text in other_pages), "the machined part left the visual summary"
    assert not any(MACHINED in text for text in hardware_pages), "the machined part is listed as hardware"


# -- the rule ---------------------------------------------------------------


@pytest.mark.parametrize(
    "attrs, processes, expected",
    [
        ({}, ["hardware"], True),
        ({"process": "Fasteners"}, [], True),
        ({"category": "Fastener"}, ["hardware"], True),
        ({"category": "Hardware"}, [], False),
        ({"category": "Hardware"}, ["machine"], False),
        ({"process": "hardware coating"}, [], False),
        ({"folder": r"C:\SOLIDWORKS Data\Toolbox\ansi inch\bolts"}, ["purchase"], True),
        ({"filepath": r"D:\Library\Fasteners\M6x20.SLDPRT"}, ["purchase"], True),
        ({"folder": r"C:\Projects\Frame"}, ["machine"], False),
        ({}, [], False),
    ],
)
def test_hardware_is_a_process_or_a_folder_never_a_category(app, attrs, processes, expected):
    with app.app_context():
        assert is_hardware(attrs, processes, app.config["PROCESS_META"]) is expected


def test_a_catalogue_without_the_fasteners_alias_cannot_hide_one(app):
    meta = load_process_meta(overrides={"hardware": {"aliases": []}})
    with app.app_context():
        # The resolver files "Fasteners" under "others" here; the raw column
        # still says what the part is.
        assert is_hardware({"process": "Fasteners"}, ["others"], meta) is True


def test_a_folder_named_hardware_later_counts_without_a_recompute(app):
    attrs = {"process": "Purchase", "folder": r"D:\Library\Bolts"}
    with app.app_context():
        assert is_hardware(attrs, ["purchase"], app.config["PROCESS_META"]) is False
        app.config["HARDWARE_FOLDERS"] = ["bolts"]
        assert is_hardware(attrs, ["purchase"], app.config["PROCESS_META"]) is True


def test_classification_follows_the_rule(app):
    with app.app_context():
        meta = app.config["PROCESS_META"]
        toolbox = {"folder": r"C:\SOLIDWORKS Data\Toolbox\ansi metric\washers"}
        assert classify_part(toolbox, ["purchase"], meta) == "hardware"
        assert classify_part({}, ["hardware"], meta, category="Fastener") == "hardware"
        # Category still sorts the other classes; it just no longer makes or
        # unmakes hardware.
        assert classify_part({}, [], meta, category="Hardware") == "fabrication"
        assert classify_part({}, [], meta, category="Purchased") == "purchase"


# -- doc packs --------------------------------------------------------------


def test_standalone_visual_summary_moves_every_kind_of_hardware_to_its_end(app, tmp_path):
    # On its own the visual summary still closes with the hardware it left out.
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    _build_assembly(app, str(tmp_path))

    with app.app_context():
        _name, data, mime = build_docpack(_opts(want_visual_list=True))

    assert mime == "application/pdf"
    _assert_partitioned(_pages(data))


def test_standalone_hardware_summary_lists_every_kind_of_hardware(app, tmp_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    _build_assembly(app, str(tmp_path))

    with app.app_context():
        _name, data, _mime = build_docpack(_opts(want_hardware_summary=True))

    text = "\n".join(_pages(data))
    for pn in HARDWARE:
        assert pn in text, f"{pn} is missing from the hardware summary"
    assert MACHINED not in text


def test_visual_summary_with_its_hardware_summary_splits_the_parts(app, tmp_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    _build_assembly(app, str(tmp_path))

    with app.app_context():
        _name, data, _mime = build_docpack(_opts(want_visual_list=True, want_hardware_summary=True))

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        visual = next(n for n in z.namelist() if "Visual" in n)
        _assert_partitioned(_pages(z.read(visual)))


def test_binder_visual_summary_splits_the_parts(app, tmp_path):
    # The root and the machined part have drawings, so the binder takes the
    # path that redraws the visual summary with page numbers.
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    _build_assembly(app, str(tmp_path))

    with app.app_context():
        _name, data, mime = build_docpack(_opts(want_pdf_binder=True))

    assert mime == "application/pdf"
    pages = _pages(data)
    assert any(f"{MACHINED} DRAWING" in text for text in pages)
    _assert_partitioned(pages)


def test_fabrication_binder_index_points_at_the_right_pages(app, tmp_path):
    """The page-numbered visual summary must draw the cards the index counted.

    A fabrication pack's first pass lists the parts consumed into a weldment;
    the redraw used to walk the BOM again without them. With enough of them to
    fill a second visual page, the index counted two pages the binder no longer
    had, and every page number in it pointed one page too far.
    """
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    Part(part_number="FB-100", revision="1", description="SKID ASSEMBLY", processes=["assembly"]).save()
    Part(part_number="FB-200", revision="1", description="WELDED FRAME", processes=["welding"]).save()
    BOMLink(parent_pn="FB-100", parent_rev="1", child_pn="FB-200", child_rev="1", qty=1).save()
    _drawing(str(tmp_path), "FB-100", "1")
    _drawing(str(tmp_path), "FB-200", "1")
    plates = [f"FB-3{i:02d}" for i in range(13)]
    for pn in plates:
        Part(part_number=pn, revision="1", description="GUSSET PLATE", processes=["lasercut"]).save()
        BOMLink(parent_pn="FB-200", parent_rev="1", child_pn=pn, child_rev="1", qty=2).save()
        _drawing(str(tmp_path), pn, "1")

    with app.app_context():
        _name, data, _mime = build_docpack(DocPackOptions(root_pn="FB-100", root_rev="1", fabrication_pack=True))

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        binder = next(n for n in z.namelist() if n.endswith(".pdf") and "Binder" in n)
        pages = _pages(z.read(binder))

    index_text = next(text for text in pages if "Index" in text and "WELDED FRAME" in text)
    for pn, desc in [("FB-200", "WELDED FRAME")] + [(pn, "GUSSET PLATE") for pn in plates]:
        listed = re.search(rf"{re.escape(pn)} - {desc}[\s.]*(\d+)", index_text)
        assert listed, f"{pn} is missing from the index"
        actual = next(i + 1 for i, text in enumerate(pages) if f"{pn} DRAWING" in text)
        assert int(listed.group(1)) == actual, f"the index sends {pn} to page {listed.group(1)}, it is on {actual}"


def test_category_never_vetoes_a_hardware_process(app, tmp_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    Part(part_number="ASM-HWOVR", revision="", description="Root Assembly", processes=["assembly"]).save()
    Part(part_number="HW-OVR", revision="", description="Washer", processes=["hardware"], category="part").save()
    BOMLink(parent_pn="ASM-HWOVR", parent_rev="", child_pn="HW-OVR", child_rev="", qty=2).save()

    with app.app_context():
        _, data, _ = build_docpack(
            DocPackOptions(root_pn="ASM-HWOVR", root_rev="", want_selected_files=False, want_hardware_summary=True)
        )
    text = "\n".join(_pages(data))
    assert "HW-OVR" in text
    assert "No hardware items found" not in text


# -- the other lists --------------------------------------------------------


def _admin_client(client):
    role = Role(name="administrator", permissions=sorted(PERMISSION_REGISTRY)).save()
    admin = User(email="hw-admin@example.com", password="test", active=True, fs_uniquifier="hw-admin", roles=[role]).save()
    with client.session_transaction() as sess:
        sess["_user_id"] = admin.get_id()


def _csv_rows(resp):
    return list(csv.DictReader(io.StringIO(resp.data.decode("utf-8-sig"))))


def test_arena_exports_treat_a_toolbox_part_as_hardware(client, app, tmp_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILE_SOURCES"] = [{"local_root": str(tmp_path)}]
    _admin_client(client)
    _build_assembly(app, str(tmp_path))
    _drawing(str(tmp_path), BY_TOOLBOX, "")

    resp = client.post(f"/api/parts/{ROOT}/export/arena_bom", json={"rev": "1"})
    assert resp.status_code == 200
    procurement = {row["item number"]: row["procurement type"] for row in _csv_rows(resp)}
    assert procurement[MACHINED] == "MTS"
    for pn in HARDWARE:
        assert procurement[pn] == "OTS", f"{pn} is hardware, so it is bought in"

    resp = client.post(
        f"/api/parts/{ROOT}/export/arena_file_links",
        json={"rev": "1", "base_url": "https://example.com/arena"},
    )
    assert resp.status_code == 200
    linked = {row["item number"] for row in _csv_rows(resp)}
    assert MACHINED in linked
    assert BY_TOOLBOX not in linked, "hardware gets no Arena file links"
