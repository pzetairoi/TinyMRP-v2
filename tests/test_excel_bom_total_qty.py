import io
import zipfile

from openpyxl import load_workbook

from app.models.part import Part
from app.models.bom import BOMLink
from app.services.docpacks import DocPackOptions, build_docpack


def test_excel_bom_uses_total_qty_header(app):
    root = Part(part_number="ASM-200", revision="", description="Root").save()
    child = Part(part_number="C-1", revision="", description="Child").save()
    BOMLink(parent_pn=root.part_number, parent_rev="", child_pn=child.part_number, child_rev="", qty=2).save()

    opts = DocPackOptions(
        root_pn=root.part_number,
        root_rev="",
        depth="full",
        include_consumed=True,
        want_excel_bom=True,
        want_selected_files=False,
        want_pdf_binder=False,
        want_visual_list=False,
    )

    with app.app_context():
        name, data, mime = build_docpack(opts)

    assert mime == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(data))
    bom_name = next(n for n in zf.namelist() if n.lower().endswith(".xlsx"))
    wb = load_workbook(io.BytesIO(zf.read(bom_name)))
    ws = wb.active
    header_row = next(ws.iter_rows(min_row=1, max_row=1))
    header = [str(c.value or "").strip().lower() for c in header_row]

    assert "total qty" in header
    assert all("approved" not in h for h in header)
