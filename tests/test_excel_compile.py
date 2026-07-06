import io
import os
import uuid
import zipfile

import openpyxl
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader

from app.models.auth import Role, User
from app.models.part import Part
from app.models.bom import BOMLink
from app.models.artifact import PartFile
from app.services.excel_compile import CompileRow, build_excel_compile_zip


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _tools_user():
    role = Role.objects(name="admin").first() or Role(name="admin").save()
    return User(
        email=f"tools-{uuid.uuid4()}@example.com",
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=[role],
    ).save()


def _write_pdf(path: str, label: str) -> None:
    c = canvas.Canvas(path)
    c.drawString(100, 750, label)
    c.showPage()
    c.save()


def test_excel_compile_binder_merges_all_pdfs(app, tmp_path):
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    root = Part(part_number="AWS-B-001597", revision="1", description="BEARING CLAMP DRIVE - WELDMENT",
                processes=["welding"], attrs={"material": "REFER TO BOM", "finish": "ZINC", "mass": 0.9}).save()
    child = Part(part_number="AWS-A-001596", revision="1", description="BEARING CLAMP DRIVE PLATE",
                 processes=["lasercut", "machine"], attrs={"material": "MS - GR250", "finish": "NATURAL", "mass": 0.7}).save()
    hw = Part(part_number="B18.3.5M-16x2.0x55", revision="", description="COUNTER SINK SCREW",
              processes=["hardware"]).save()
    BOMLink(parent_pn=root.part_number, parent_rev="1", child_pn=child.part_number, child_rev="1", qty=1).save()
    BOMLink(parent_pn=root.part_number, parent_rev="1", child_pn=hw.part_number, child_rev="", qty=6).save()

    root_pdf = os.path.join(root_dir, "AWS-B-001597.pdf")
    child_pdf = os.path.join(root_dir, "AWS-A-001596.pdf")
    _write_pdf(root_pdf, "ROOT WELDMENT PDF")
    _write_pdf(child_pdf, "CHILD PLATE PDF")
    PartFile(part_number=root.part_number, revision="1", ext_group="pdf", ext="pdf",
              rel_path="AWS-B-001597.pdf", path=root_pdf).save()
    PartFile(part_number=child.part_number, revision="1", ext_group="pdf", ext="pdf",
              rel_path="AWS-A-001596.pdf", path=child_pdf).save()

    rows = [CompileRow(part_number=root.part_number, revision="1", qty=1.0, status="ok")]

    with app.app_context():
        data, missing = build_excel_compile_zip(
            rows,
            input_filename="input.xlsx",
            input_bytes=b"fake-xlsx-bytes",
            file_root=str(root_dir),
            want_excel_bom=True,
            want_pdf_binder=True,
            binder_add_cover=True,
            binder_add_index=True,
            binder_add_visual_list=True,
            binder_add_hardware_summary=True,
            binder_page_numbers=True,
            title="Quote 12345",
        )

    assert not missing
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        binder_name = next((n for n in names if "Binder" in n and n.lower().endswith(".pdf")), None)
        assert binder_name, f"No Binder.pdf found in output zip: {names}"
        binder_bytes = zf.read(binder_name)

    reader = PdfReader(io.BytesIO(binder_bytes))
    full = "\n".join((p.extract_text() or "") for p in reader.pages)
    assert "ROOT WELDMENT PDF" in full, "root part's own PDF missing from compiled binder"
    assert "CHILD PLATE PDF" in full, "child part's own PDF missing from compiled binder"

    cover_text = reader.pages[0].extract_text() or ""
    assert cover_text.count("Generated") == 1, f"expected a single Generated date on the cover, got:\n{cover_text}"


def _make_compile_xlsx(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "COMPILE"
    ws.append(["PartNumber", "Revision", "Qty"])
    for pn, rev, qty in rows:
        ws.append([pn, rev, qty])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_excel_compile_view_wires_whereused_and_datasheets(app, client, tmp_path):
    """The Excel Compile form was restyled to match the Part Detail docpack
    builder; this locks in that the newly-added Where-used/Datasheets
    checkboxes actually reach build_excel_compile_zip end-to-end via the view.
    """
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    with app.app_context():
        user = _tools_user()
        root = Part(part_number="ASM-VIEW", revision="1", description="Root Assembly", processes=["assembly"]).save()
        root_pdf = os.path.join(root_dir, "ASM-VIEW.pdf")
        _write_pdf(root_pdf, "ROOT VIEW PDF")
        PartFile(part_number=root.part_number, revision="1", ext_group="pdf", ext="pdf",
                  rel_path="ASM-VIEW.pdf", path=root_pdf).save()

    _login(client, user)
    xlsx_bytes = _make_compile_xlsx([("ASM-VIEW", "1", 1)])

    resp = client.post(
        "/tools/excelcompile",
        data={
            "file": (io.BytesIO(xlsx_bytes), "compile.xlsx"),
            "title": "View Test",
            "want_pdf_binder": "on",
            "binder_add_whereused": "on",
            "binder_add_datasheets": "on",
            "want_whereused_report": "on",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Compile Complete" in body
    assert "No missing parts" in body
