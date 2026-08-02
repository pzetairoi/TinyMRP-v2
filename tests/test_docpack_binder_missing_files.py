import io
import os

from reportlab.pdfgen import canvas
from pypdf import PdfReader

from app.models.part import Part
from app.models.bom import BOMLink
from app.models.artifact import PartFile
from app.services.docpacks import DocPackOptions, build_docpack


def _write_pdf(path: str, label: str) -> None:
    c = canvas.Canvas(path)
    c.drawString(100, 750, label)
    c.showPage()
    c.save()


def test_binder_surfaces_missing_source_file(app, tmp_path):
    """Simulates a failed upload: a PartFile row exists in Mongo but the
    actual PDF never landed on the deliverables volume (e.g. a container
    permission/UID mismatch during upload). The binder must not silently
    drop the page -- it must say so, and page numbering must stay correct.
    """
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    root = Part(part_number="ASM-MISS", revision="1", description="Root Assembly", processes=["assembly"]).save()
    child = Part(part_number="CHILD-MISS", revision="1", description="Missing Child Plate", processes=["lasercut"]).save()
    BOMLink(parent_pn=root.part_number, parent_rev="1", child_pn=child.part_number, child_rev="1", qty=1).save()

    root_pdf = os.path.join(root_dir, "ASM-MISS.pdf")
    _write_pdf(root_pdf, "ROOT PDF PRESENT")
    PartFile(part_number=root.part_number, revision="1", ext_group="pdf", ext="pdf",
              rel_path="ASM-MISS.pdf", path=root_pdf).save()

    # Child's PartFile record exists, but the file was never actually written.
    PartFile(part_number=child.part_number, revision="1", ext_group="pdf", ext="pdf",
              rel_path="CHILD-MISS.pdf", path=os.path.join(root_dir, "CHILD-MISS.pdf")).save()

    opts = DocPackOptions(
        root_pn=root.part_number,
        root_rev="1",
        want_pdf_binder=True,
        want_selected_files=False,
        binder_add_cover=False,
        binder_add_index=True,
        binder_add_visual_list=False,
        binder_add_hardware_summary=False,
        binder_page_numbers=False,
    )
    with app.app_context():
        name, data, mime = build_docpack(opts)

    assert mime == "application/pdf", "expected a single merged PDF, not a zip"
    reader = PdfReader(io.BytesIO(data))
    full = "\n".join((p.extract_text() or "") for p in reader.pages)
    assert "ROOT PDF PRESENT" in full
    assert "Missing Source Documents" in full
    assert "CHILD-MISS" in full
