import io
import os
import re
import zipfile

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


def _collect_stream_bytes(page) -> list[bytes]:
    streams: list[bytes] = []
    contents = page.get_contents()
    if contents is not None:
        if isinstance(contents, list):
            streams.extend([c.get_data() for c in contents if c])
        else:
            streams.append(contents.get_data())

    def _walk_xobj(obj, seen: set[int]) -> None:
        try:
            o = obj.get_object()
        except Exception:
            return
        if id(o) in seen:
            return
        seen.add(id(o))
        try:
            if o.get("/Subtype") == "/Form":
                try:
                    data = o.get_data()
                    if data:
                        streams.append(data)
                except Exception:
                    pass
                res = o.get("/Resources") or {}
                xobjs = res.get("/XObject") or {}
                for child in xobjs.values():
                    _walk_xobj(child, seen)
        except Exception:
            return

    try:
        resources = page.get("/Resources") or {}
        xobjs = resources.get("/XObject") or {}
        for x in xobjs.values():
            _walk_xobj(x, set())
    except Exception:
        pass
    return streams


def _stream_text(page) -> str:
    texts = []
    for data in _collect_stream_bytes(page):
        try:
            texts.append(data.decode("latin1", errors="ignore"))
        except Exception:
            pass
    return "\n".join(t for t in texts if t)


def _page_text(page) -> str:
    parts = []
    try:
        txt = page.extract_text() or ""
        if txt:
            parts.append(txt)
    except Exception:
        pass
    stream_txt = _stream_text(page)
    if stream_txt:
        parts.append(stream_txt)
    return "\n".join(parts)


def _has_center_translate(page, width: float, height: float) -> bool:
    text = _stream_text(page)
    for m in re.finditer(r"([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\s+cm", text):
        try:
            tx = float(m.group(5))
            ty = float(m.group(6))
        except Exception:
            continue
        if abs(tx - (width / 2.0)) < 12 and abs(ty - (height / 2.0)) < 12:
            return True
    return False


def _has_box_strokes(page) -> bool:
    text = _stream_text(page)
    if " re" not in text:
        return False
    widths = []
    for m in re.finditer(r"([0-9.]+)\s+w", text):
        try:
            widths.append(float(m.group(1)))
        except Exception:
            pass
    return any(w >= 1.0 for w in widths)


def _page_has_number(page, idx: int, total: int) -> bool:
    pattern = rf"{idx}\s*/\s*{total}"
    text = _page_text(page)
    if re.search(pattern, text):
        return True
    # Fallback: scan stream content for literal number tokens in case extract_text fails.
    stream_text = _stream_text(page)
    return bool(re.search(pattern, stream_text))


def _count_phrase(reader, phrase: str) -> int:
    count = 0
    for page in reader.pages:
        text = _page_text(page)
        if not text:
            continue
        count += text.lower().count(phrase.lower())
    return count


def test_binder_has_numbers_visual_boxes_and_center_stamp(app, tmp_path):
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    root = Part(part_number="ASM-100", revision="", description="Root Assembly", processes=["assembly"]).save()
    child = Part(part_number="HW-10", revision="", description="Bolt", processes=["hardware"]).save()

    BOMLink(parent_pn=root.part_number, parent_rev="", child_pn=child.part_number, child_rev="", qty=4).save()

    pdf_path = os.path.join(root_dir, "ASM-100.pdf")
    _write_pdf(pdf_path, "ROOT PDF")
    PartFile(
        part_number=root.part_number,
        revision="",
        ext_group="pdf",
        ext="pdf",
        rel_path="ASM-100.pdf",
        path=pdf_path,
    ).save()

    opts = DocPackOptions(
        root_pn=root.part_number,
        root_rev="",
        depth="full",
        include_consumed=True,
        want_pdf_binder=True,
        want_visual_list=True,
        binder_page_numbers=True,
        binder_add_hardware_summary=True,
        stamp_inprogress=True,
    )

    with app.app_context():
        name, data, mime = build_docpack(opts)

    assert mime == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(data))
    binder_name = next(n for n in zf.namelist() if "Binder" in n and n.lower().endswith(".pdf"))
    visual_name = next(n for n in zf.namelist() if "VisualList" in n and n.lower().endswith(".pdf"))
    binder_bytes = zf.read(binder_name)
    visual_bytes = zf.read(visual_name)

    reader = PdfReader(io.BytesIO(binder_bytes))
    assert len(reader.pages) >= 3
    total = len(reader.pages)

    cover_text = _page_text(reader.pages[0])
    assert "Generated:" in cover_text
    assert "ASM-100" in cover_text

    assert _count_phrase(reader, "Hardware Summary") >= 2

    numbered = True
    for idx, page in enumerate(reader.pages, start=1):
        if idx == 1:
            continue
        if not _page_has_number(page, idx, total):
            numbered = False
            break
    assert numbered

    page = reader.pages[1]
    assert _has_center_translate(page, float(page.mediabox.width), float(page.mediabox.height))

    vreader = PdfReader(io.BytesIO(visual_bytes))
    assert _has_box_strokes(vreader.pages[0])


def test_hardware_summary_standalone(app, tmp_path):
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    root = Part(part_number="ASM-200", revision="", description="Root Assembly", processes=["assembly"]).save()
    child = Part(part_number="HW-20", revision="", description="Washer", processes=["hardware"]).save()

    BOMLink(parent_pn=root.part_number, parent_rev="", child_pn=child.part_number, child_rev="", qty=6).save()

    opts = DocPackOptions(
        root_pn=root.part_number,
        root_rev="",
        depth="full",
        include_consumed=True,
        want_selected_files=False,
        want_hardware_summary=True,
    )

    with app.app_context():
        name, data, mime = build_docpack(opts)

    assert mime == "application/pdf"
    assert "HardwareSummary" in name
    reader = PdfReader(io.BytesIO(data))
    assert len(reader.pages) >= 1
    assert "Hardware Summary" in _page_text(reader.pages[0])
