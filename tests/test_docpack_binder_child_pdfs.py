import io
import os

from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader

from app.models.part import Part
from app.models.bom import BOMLink
from app.models.artifact import PartFile
from app.services.docpacks import DocPackOptions, build_docpack


def _write_pdf(path: str, label: str) -> None:
    c = canvas.Canvas(path)
    c.drawString(100, 750, label)
    c.showPage()
    c.save()


def test_binder_merges_child_part_own_pdf(app, tmp_path):
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

    opts = DocPackOptions(
        root_pn=root.part_number,
        root_rev="1",
        depth="full",
        include_consumed=True,
        want_pdf_binder=True,
        want_selected_files=False,
        binder_add_cover=True,
        binder_add_index=True,
        binder_add_visual_list=True,
        binder_add_hardware_summary=True,
        binder_page_numbers=True,
    )

    with app.app_context():
        name, data, mime = build_docpack(opts)

    assert mime == "application/pdf", "expected a single merged PDF, not a zip"
    reader = PdfReader(io.BytesIO(data))
    full = "\n".join((p.extract_text() or "") for p in reader.pages)
    assert "ROOT WELDMENT PDF" in full, "root part's own PDF missing from binder body"
    assert "CHILD PLATE PDF" in full, "child part's own PDF missing from binder body"
