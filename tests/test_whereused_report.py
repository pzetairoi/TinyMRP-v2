import io

from PyPDF2 import PdfReader

from app.models.part import Part
from app.models.bom import BOMLink
from app.services.docpacks import DocPackOptions, build_docpack


def _first_page_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    if not reader.pages:
        return ""
    try:
        return reader.pages[0].extract_text() or ""
    except Exception:
        return ""


def test_whereused_report_standalone(app):
    child = Part(part_number="CH-1", revision="", description="Child", processes=["machine"]).save()
    parent = Part(part_number="ASM-1", revision="", description="Parent", processes=["assembly"]).save()
    BOMLink(parent_pn=parent.part_number, parent_rev="", child_pn=child.part_number, child_rev="", qty=2).save()

    opts = DocPackOptions(
        root_pn=child.part_number,
        root_rev="",
        want_selected_files=False,
        want_excel_bom=False,
        want_pdf_binder=False,
        want_whereused_report=True,
    )

    with app.app_context():
        name, data, mime = build_docpack(opts)

    assert mime == "application/pdf"
    assert name.lower().endswith(".pdf")
    text = _first_page_text(data)
    assert "Where Used" in text
    assert "CH-1" in text
