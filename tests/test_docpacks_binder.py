import base64
import io
import os
import re
import zipfile
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest

from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader

from app.models.app_settings import AppSettings
from app.models.part import Part
from app.models.bom import BOMLink
from app.models.artifact import PartFile
from app.services.docpacks import DocPackOptions, build_docpack
from app.services.app_settings import resolve_brand_logo_path


def _write_pdf(path: str, label: str) -> None:
    c = canvas.Canvas(path)
    c.drawString(100, 750, label)
    c.showPage()
    c.save()


def _write_png(path: str) -> None:
    raw = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/6X4Z6AAAAAASUVORK5CYII="
    )
    with open(path, "wb") as fh:
        fh.write(raw)


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


def _has_xobject(page) -> bool:
    try:
        resources = page.get("/Resources") or {}
        xobjs = resources.get("/XObject") or {}
        return bool(xobjs)
    except Exception:
        return False


def _safe_zoneinfo(name: str):
    try:
        return ZoneInfo(name)
    except Exception:
        return None


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
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
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
    text = _page_text(reader.pages[0])
    assert "Hardware Summary" in text
    assert "Finish" not in text


def test_index_pdf_standalone(app, tmp_path):
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    root = Part(part_number="ASM-IDX", revision="", description="Root Assembly", processes=["assembly"]).save()
    pdf_path = os.path.join(root_dir, "ASM-IDX.pdf")
    _write_pdf(pdf_path, "ROOT PDF")
    PartFile(
        part_number=root.part_number,
        revision="",
        ext_group="pdf",
        ext="pdf",
        rel_path="ASM-IDX.pdf",
        path=pdf_path,
    ).save()

    opts = DocPackOptions(
        root_pn=root.part_number,
        root_rev="",
        want_selected_files=False,
        want_index_pdf=True,
    )

    with app.app_context():
        name, data, mime = build_docpack(opts)

    assert mime == "application/pdf"
    assert "Index" in name
    reader = PdfReader(io.BytesIO(data))
    text = _page_text(reader.pages[0])
    assert "Index" in text
    assert root.part_number in text


def test_index_pdf_in_zip(app, tmp_path):
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    root = Part(part_number="ASM-IDXZIP", revision="", description="Root Assembly", processes=["assembly"]).save()
    pdf_path = os.path.join(root_dir, "ASM-IDXZIP.pdf")
    _write_pdf(pdf_path, "ROOT PDF")
    PartFile(
        part_number=root.part_number,
        revision="",
        ext_group="pdf",
        ext="pdf",
        rel_path="ASM-IDXZIP.pdf",
        path=pdf_path,
    ).save()

    opts = DocPackOptions(
        root_pn=root.part_number,
        root_rev="",
        want_selected_files=False,
        want_index_pdf=True,
        want_visual_list=True,
    )

    with app.app_context():
        name, data, mime = build_docpack(opts)

    assert mime == "application/zip"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
    assert any("Index" in n and n.lower().endswith(".pdf") for n in names)
    assert any("VisualList" in n and n.lower().endswith(".pdf") for n in names)


def test_flat_pattern_filtered_by_default(app, tmp_path):
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    root = Part(part_number="ASM-FLAT", revision="", description="Bracket", processes=["assembly"]).save()
    main_path = os.path.join(root_dir, "ASM-FLAT_main.pdf")
    flat_path = os.path.join(root_dir, "ASM-FLAT_flat-pattern.pdf")
    _write_pdf(main_path, "MAIN PDF")
    _write_pdf(flat_path, "FLAT PDF")
    PartFile(
        part_number=root.part_number,
        revision="",
        ext_group="pdf",
        ext="pdf",
        rel_path="ASM-FLAT_main.pdf",
        path=main_path,
    ).save()
    PartFile(
        part_number=root.part_number,
        revision="",
        ext_group="pdf",
        ext="pdf",
        rel_path="ASM-FLAT_flat-pattern.pdf",
        path=flat_path,
        is_dwg=True,
    ).save()

    opts = DocPackOptions(
        root_pn=root.part_number,
        root_rev="",
        want_selected_files=False,
        want_index_pdf=True,
    )
    with app.app_context():
        _, data, _ = build_docpack(opts)
    text = _page_text(PdfReader(io.BytesIO(data)).pages[0])
    assert "pdf 2" not in text.lower()

    opts2 = DocPackOptions(
        root_pn=root.part_number,
        root_rev="",
        want_selected_files=False,
        want_index_pdf=True,
        binder_include_flat_patterns=True,
    )
    with app.app_context():
        _, data2, _ = build_docpack(opts2)
    text2 = _page_text(PdfReader(io.BytesIO(data2)).pages[0])
    assert "pdf 2" in text2.lower()


def test_index_label_avoids_long_filenames(app, tmp_path):
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    root = Part(part_number="ASM-LABEL", revision="", description="Root Assembly", processes=["assembly"]).save()
    long_a = "VERY_LONG_UNISTRUT_NUT_DETAIL_DRAWING_2024_REV_A"
    long_b = "VERY_LONG_UNISTRUT_NUT_DETAIL_DRAWING_2024_REV_B"
    pdf_a = os.path.join(root_dir, f"{long_a}.pdf")
    pdf_b = os.path.join(root_dir, f"{long_b}.pdf")
    _write_pdf(pdf_a, "DOC A")
    _write_pdf(pdf_b, "DOC B")
    PartFile(
        part_number=root.part_number,
        revision="",
        ext_group="pdf",
        ext="pdf",
        rel_path=f"{long_a}.pdf",
        path=pdf_a,
    ).save()
    PartFile(
        part_number=root.part_number,
        revision="",
        ext_group="pdf",
        ext="pdf",
        rel_path=f"{long_b}.pdf",
        path=pdf_b,
        is_dwg=True,
    ).save()

    opts = DocPackOptions(
        root_pn=root.part_number,
        root_rev="",
        want_selected_files=False,
        want_index_pdf=True,
        binder_include_flat_patterns=True,
    )
    with app.app_context():
        _, data, _ = build_docpack(opts)
    text = _page_text(PdfReader(io.BytesIO(data)).pages[0])
    assert long_a not in text
    assert long_b not in text


def test_hardware_category_override(app, tmp_path):
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    root = Part(part_number="ASM-HWOVR", revision="", description="Root Assembly", processes=["assembly"]).save()
    child = Part(
        part_number="HW-OVR",
        revision="",
        description="Washer",
        processes=["hardware"],
        category="part",
    ).save()
    BOMLink(parent_pn=root.part_number, parent_rev="", child_pn=child.part_number, child_rev="", qty=2).save()

    opts = DocPackOptions(
        root_pn=root.part_number,
        root_rev="",
        want_selected_files=False,
        want_hardware_summary=True,
    )
    with app.app_context():
        _, data, _ = build_docpack(opts)
    text = _page_text(PdfReader(io.BytesIO(data)).pages[0])
    assert "No hardware items found" in text


def test_timezone_setting_applies_to_docpack(app, tmp_path):
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    AppSettings.objects.delete()
    AppSettings(timezone="Australia/Melbourne").save()

    tz = _safe_zoneinfo("Australia/Melbourne")
    if tz is None:
        pytest.skip("tzdata not available for ZoneInfo")

    root = Part(part_number="ASM-TZ", revision="", description="Root Assembly", processes=["assembly"]).save()
    pdf_path = os.path.join(root_dir, "ASM-TZ.pdf")
    _write_pdf(pdf_path, "ROOT PDF")
    PartFile(
        part_number=root.part_number,
        revision="",
        ext_group="pdf",
        ext="pdf",
        rel_path="ASM-TZ.pdf",
        path=pdf_path,
    ).save()

    build_ts = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    expected = build_ts.astimezone(tz).strftime("%Y-%m-%d %H:%M")
    opts = DocPackOptions(
        root_pn=root.part_number,
        root_rev="",
        want_selected_files=False,
        want_cover_page=True,
        build_ts=build_ts,
    )
    with app.app_context():
        _, data, _ = build_docpack(opts)
    text = _page_text(PdfReader(io.BytesIO(data)).pages[0])
    assert expected in text


def test_custom_logo_used_in_docpack(app, tmp_path):
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    brand_dir = os.path.join(root_dir, "_branding")
    os.makedirs(brand_dir, exist_ok=True)
    logo_path = os.path.join(brand_dir, "logo.png")
    _write_png(logo_path)

    AppSettings.objects.delete()
    AppSettings(brand_logo_rel_path="_branding/logo.png").save()

    root = Part(part_number="ASM-LOGO", revision="", description="Root Assembly", processes=["assembly"]).save()
    pdf_path = os.path.join(root_dir, "ASM-LOGO.pdf")
    _write_pdf(pdf_path, "ROOT PDF")
    PartFile(
        part_number=root.part_number,
        revision="",
        ext_group="pdf",
        ext="pdf",
        rel_path="ASM-LOGO.pdf",
        path=pdf_path,
    ).save()

    opts = DocPackOptions(
        root_pn=root.part_number,
        root_rev="",
        want_selected_files=False,
        want_cover_page=True,
    )
    with app.app_context():
        resolved = resolve_brand_logo_path()
        assert resolved and os.path.isfile(resolved)
        _, data, _ = build_docpack(opts)
    reader = PdfReader(io.BytesIO(data))
    assert len(reader.pages) >= 1
