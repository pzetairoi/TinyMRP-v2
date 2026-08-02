from __future__ import annotations

import io
import math
import os
from dataclasses import dataclass
from html import escape
from typing import Any, Iterable

from flask import current_app

from app.models.artifact import PartFile
from app.models.part_drawing_markup import PartDrawingMarkup
from app.services.filenames import build_output_name
from app.services.part_drawing_markups import source_fingerprint_for
from app.services.part_norm import clean_rev


@dataclass
class MarkupDocument:
    part_number: str
    revision: str
    filename: str
    pdf_bytes: bytes


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _fmt(value: Any) -> str:
    return f"{_number(value):.4f}".rstrip("0").rstrip(".") or "0"


def _paint(value: Any, default: str = "none") -> str:
    text = str(value or "").strip()
    if not text:
        return default
    if text.startswith("#") or text.startswith("rgb") or text.lower() in {
        "black", "white", "red", "blue", "green", "yellow", "orange", "purple", "gray", "grey",
    }:
        return escape(text, quote=True)
    return default


def _origin_offset(origin: Any, size: float) -> float:
    value = str(origin or "center").lower()
    if value in ("left", "top"):
        return 0.0
    if value in ("right", "bottom"):
        return -size
    return -size / 2.0


def _transform(obj: dict[str, Any]) -> str:
    left = _number(obj.get("left"))
    top = _number(obj.get("top"))
    angle = _number(obj.get("angle"))
    scale_x = _number(obj.get("scaleX"), 1.0) * (-1 if obj.get("flipX") else 1)
    scale_y = _number(obj.get("scaleY"), 1.0) * (-1 if obj.get("flipY") else 1)
    skew_x = _number(obj.get("skewX"))
    skew_y = _number(obj.get("skewY"))
    values = [f"translate({_fmt(left)} {_fmt(top)})"]
    if angle:
        values.append(f"rotate({_fmt(angle)})")
    if skew_x:
        values.append(f"skewX({_fmt(skew_x)})")
    if skew_y:
        values.append(f"skewY({_fmt(skew_y)})")
    if scale_x != 1 or scale_y != 1:
        values.append(f"scale({_fmt(scale_x)} {_fmt(scale_y)})")
    return " ".join(values)


def _style(obj: dict[str, Any]) -> str:
    stroke = _paint(obj.get("stroke"))
    fill = _paint(obj.get("fill"))
    width = max(0.25, _number(obj.get("strokeWidth"), 1.0))
    opacity = min(1.0, max(0.0, _number(obj.get("opacity"), 1.0)))
    dash = obj.get("strokeDashArray")
    attrs = [
        f'stroke="{stroke}"',
        f'fill="{fill}"',
        f'stroke-width="{_fmt(width)}"',
        f'opacity="{_fmt(opacity)}"',
        f'stroke-linecap="{escape(str(obj.get("strokeLineCap") or "round"), quote=True)}"',
        f'stroke-linejoin="{escape(str(obj.get("strokeLineJoin") or "round"), quote=True)}"',
    ]
    if isinstance(dash, list) and dash:
        attrs.append(f'stroke-dasharray="{" ".join(_fmt(value) for value in dash)}"')
    return " ".join(attrs)


def _path_bounds(path: list) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for command in path:
        if not isinstance(command, list) or not command:
            continue
        values = command[1:]
        for index in range(0, len(values) - 1, 2):
            xs.append(_number(values[index]))
            ys.append(_number(values[index + 1]))
    if not xs or not ys:
        return (0, 0, 0, 0)
    return (min(xs), min(ys), max(xs), max(ys))


def _path_data(path: list) -> str:
    chunks: list[str] = []
    for command in path:
        if not isinstance(command, list) or not command:
            continue
        op = str(command[0]).upper()
        if op not in {"M", "L", "C", "Q", "Z"}:
            continue
        chunks.append(op if op == "Z" else f"{op} {' '.join(_fmt(value) for value in command[1:])}")
    return " ".join(chunks)


def _object_svg(obj: dict[str, Any]) -> str:
    if not isinstance(obj, dict) or obj.get("visible") is False:
        return ""
    kind = str(obj.get("type") or "").lower()
    transform = _transform(obj)
    style = _style(obj)
    width = max(0.0, _number(obj.get("width")))
    height = max(0.0, _number(obj.get("height")))
    x = _origin_offset(obj.get("originX"), width)
    y = _origin_offset(obj.get("originY"), height)

    if kind == "group":
        children = "".join(_object_svg(child) for child in (obj.get("objects") or []))
        return f'<g transform="{transform}">{children}</g>'
    if kind == "rect":
        return f'<rect transform="{transform}" x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(width)}" height="{_fmt(height)}" {_style(obj)}/>'
    if kind == "ellipse":
        return f'<ellipse transform="{transform}" cx="{_fmt(x + width / 2)}" cy="{_fmt(y + height / 2)}" rx="{_fmt(width / 2)}" ry="{_fmt(height / 2)}" {style}/>'
    if kind == "line":
        return f'<line transform="{transform}" x1="{_fmt(obj.get("x1"))}" y1="{_fmt(obj.get("y1"))}" x2="{_fmt(obj.get("x2"))}" y2="{_fmt(obj.get("y2"))}" {style}/>'
    if kind == "triangle":
        points = f"0,{_fmt(-height / 2)} {_fmt(width / 2)},{_fmt(height / 2)} {_fmt(-width / 2)},{_fmt(height / 2)}"
        return f'<polygon transform="{transform}" points="{points}" {style}/>'
    if kind in {"textbox", "text", "i-text"}:
        font_size = max(6.0, _number(obj.get("fontSize"), 18.0))
        font = escape(str(obj.get("fontFamily") or "Helvetica"), quote=True)
        lines = str(obj.get("text") or "").splitlines() or [""]
        spans = "".join(
            f'<tspan x="{_fmt(x)}" dy="{_fmt(font_size * (1.2 if index else 0))}">{escape(line)}</tspan>'
            for index, line in enumerate(lines)
        )
        return f'<text transform="{transform}" x="{_fmt(x)}" y="{_fmt(y + font_size)}" font-family="{font}" font-size="{_fmt(font_size)}" fill="{_paint(obj.get("fill"), "black")}" opacity="{_fmt(obj.get("opacity", 1))}">{spans}</text>'
    if kind == "path" and isinstance(obj.get("path"), list):
        path = obj["path"]
        min_x, min_y, max_x, max_y = _path_bounds(path)
        centre_x = (min_x + max_x) / 2
        centre_y = (min_y + max_y) / 2
        data = _path_data(path)
        return f'<g transform="{transform}"><path transform="translate({_fmt(-centre_x)} {_fmt(-centre_y)})" d="{escape(data, quote=True)}" {style}/></g>'
    return ""


def _visible_objects(layer: PartDrawingMarkup) -> list[dict[str, Any]]:
    objects = list((layer.canvas_json or {}).get("objects") or [])
    has_open: dict[str, bool] = {}
    for thread in layer.threads or []:
        for object_id in thread.object_ids or []:
            has_open[object_id] = has_open.get(object_id, False) or thread.status == "open"
    hidden = {object_id for object_id, open_ in has_open.items() if not open_}
    return [obj for obj in objects if isinstance(obj, dict) and str(obj.get("tmObjectId") or "") not in hidden]


def _source_path(part_file: PartFile) -> str:
    path = str(part_file.path or "")
    if os.path.isabs(path):
        return path
    root = (current_app.config.get("FILE_ROOT_LOCAL") or "").rstrip("/\\")
    rel = str(part_file.rel_path or path).replace("/", os.sep)
    return os.path.join(root, rel)


def _current_layer(pn: str, rev: str) -> tuple[PartDrawingMarkup, PartFile] | None:
    for layer in PartDrawingMarkup.objects(part_number__iexact=pn, revision__iexact=clean_rev(rev)).order_by("-updated_at"):
        try:
            source = PartFile.objects(id=layer.source_file_id).first()
        except Exception:
            source = None
        if not source or not os.path.isfile(_source_path(source)):
            continue
        if str(layer.source_fingerprint or "") != source_fingerprint_for(source):
            continue
        if _visible_objects(layer):
            return layer, source
    return None


def render_markup_pdf(layer: PartDrawingMarkup, source: PartFile) -> bytes:
    try:
        from PIL import Image
        from reportlab.graphics import renderPDF
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        from svglib.svglib import svg2rlg
    except Exception as exc:
        raise RuntimeError("Markup PDF export requires Pillow, reportlab and svglib") from exc

    source_path = _source_path(source)
    with Image.open(source_path) as image:
        width, height = image.size
    objects_svg = "".join(_object_svg(obj) for obj in _visible_objects(layer))
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f"{objects_svg}</svg>"
    )
    drawing = svg2rlg(io.BytesIO(svg.encode("utf-8")))
    if drawing is None:
        raise RuntimeError("Could not render markup vector layer")
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(width, height))
    pdf.drawImage(ImageReader(source_path), 0, 0, width=width, height=height, preserveAspectRatio=True, mask="auto")
    renderPDF.draw(drawing, pdf, 0, 0)
    pdf.save()
    return output.getvalue()


def markup_documents_for_pairs(pairs: Iterable[tuple[str, str]]) -> list[MarkupDocument]:
    documents: list[MarkupDocument] = []
    seen: set[tuple[str, str]] = set()
    for pn, rev in pairs:
        key = (str(pn or "").strip(), clean_rev(rev))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        current = _current_layer(*key)
        if not current:
            continue
        layer, source = current
        suffix = f"{key[0]}_REV_{key[1]}_Markups" if key[1] else f"{key[0]}_Markups"
        documents.append(
            MarkupDocument(
                part_number=key[0],
                revision=key[1],
                filename=build_output_name(suffix, "pdf", max_len=120, include_time=False),
                pdf_bytes=render_markup_pdf(layer, source),
            )
        )
    return documents


def markup_document_count_for_pairs(pairs: Iterable[tuple[str, str]]) -> int:
    count = 0
    seen: set[tuple[str, str]] = set()
    for pn, rev in pairs:
        key = (str(pn or "").strip(), clean_rev(rev))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        if _current_layer(*key):
            count += 1
    return count


_INDEX_ROWS_PER_PAGE = 38


def _markup_index_pdf(
    entries: list[tuple[str, str, int, int]],
    *,
    root_label: str = "",
    build_ts=None,
) -> bytes:
    """Index page(s) for the combined markup report: which parts are included
    and on which page their marked-up drawing starts (binder-style)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

    width, height = A4
    output = io.BytesIO()
    pdf = rl_canvas.Canvas(output, pagesize=A4)

    def draw_header() -> float:
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(18 * mm, height - 20 * mm, "Markup Report")
        pdf.setFont("Helvetica", 10)
        line2 = root_label.strip()
        if build_ts is not None:
            try:
                stamp = build_ts.strftime("%Y-%m-%d %H:%M")
                line2 = f"{line2}  -  {stamp}" if line2 else stamp
            except Exception:
                pass
        if line2:
            pdf.drawString(18 * mm, height - 27 * mm, line2)
        pdf.setFont("Helvetica-Bold", 9)
        y = height - 38 * mm
        pdf.drawString(18 * mm, y, "Part number")
        pdf.drawString(95 * mm, y, "Rev")
        pdf.drawString(115 * mm, y, "Pages")
        pdf.line(18 * mm, y - 2 * mm, width - 18 * mm, y - 2 * mm)
        return y - 8 * mm

    y = draw_header()
    pdf.setFont("Helvetica", 9)
    rows_on_page = 0
    for pn, rev, start_page, page_count in entries:
        if rows_on_page >= _INDEX_ROWS_PER_PAGE:
            pdf.showPage()
            y = draw_header()
            pdf.setFont("Helvetica", 9)
            rows_on_page = 0
        pages_label = str(start_page) if page_count <= 1 else f"{start_page}-{start_page + page_count - 1}"
        pdf.drawString(18 * mm, y, str(pn)[:48])
        pdf.drawString(95 * mm, y, str(rev or "-")[:12])
        pdf.drawString(115 * mm, y, pages_label)
        y -= 6 * mm
        rows_on_page += 1
    pdf.save()
    return output.getvalue()


def combine_markup_documents(
    documents: Iterable[MarkupDocument],
    *,
    include_index: bool = True,
    root_label: str = "",
    build_ts=None,
) -> bytes:
    from pypdf import PdfReader, PdfWriter

    docs = list(documents)
    readers = [PdfReader(io.BytesIO(document.pdf_bytes)) for document in docs]
    page_counts = [len(reader.pages) for reader in readers]

    writer = PdfWriter()
    if include_index and docs:
        # Page numbers must account for the index page(s) themselves.
        index_pages = max(1, math.ceil(len(docs) / _INDEX_ROWS_PER_PAGE))
        entries: list[tuple[str, str, int, int]] = []
        next_page = index_pages + 1
        for document, count in zip(docs, page_counts):
            entries.append((document.part_number, document.revision, next_page, count))
            next_page += count
        index_reader = PdfReader(
            io.BytesIO(_markup_index_pdf(entries, root_label=root_label, build_ts=build_ts))
        )
        for page in index_reader.pages:
            writer.add_page(page)
    for reader in readers:
        for page in reader.pages:
            writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
