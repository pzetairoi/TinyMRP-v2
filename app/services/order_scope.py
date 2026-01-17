from __future__ import annotations

from datetime import datetime
import io
import os
from typing import Iterable, List, Optional, Tuple
from zipfile import ZipFile, ZIP_DEFLATED

from flask import current_app
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.models.order import Order, OrderLine
from app.models.part import Part
from app.models.artifact import PartFile
from app.services.attrs import harvest_part_attrs
from app.services.docpacks import _flatten_bom, _overlay_numbers_and_stamps

_REV_BLANKS = {"", "n/a", "na", "none", "null", "nan", "0", "false"}

def _clean_rev(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in _REV_BLANKS:
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    return text.strip()


def _safe_name(value: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in (value or "").strip())


def _resolve_rev(pn: str, rev: str | None) -> str:
    if rev is None:
        p = Part.objects(part_number__iexact=pn).order_by("-updated_at").first()
        if not p:
            return ""
        attrs = harvest_part_attrs(p)
        return _clean_rev(attrs.get("revision") or p.revision or "")
    return _clean_rev(rev)


def _thumb_path(pn: str, rev: str) -> str | None:
    pf = (
        PartFile.objects(part_number__iexact=pn, revision__iexact=rev, ext_group="png", is_dwg=False)
        .only("thumb_rel_path", "rel_path", "path")
        .order_by("-thumb_rel_path", "rel_path")
        .first()
    )
    if not pf:
        return None
    root = (current_app.config.get("FILE_ROOT_LOCAL") or "").strip()
    if getattr(pf, "thumb_rel_path", None):
        return os.path.join(root, pf.thumb_rel_path.replace("/", os.sep))
    if getattr(pf, "rel_path", None):
        return os.path.join(root, pf.rel_path.replace("/", os.sep))
    if getattr(pf, "path", None):
        return pf.path
    return None


def _logo_path() -> str:
    static_dir = current_app.static_folder or ""
    return os.path.join(static_dir, "images", "logo.png")


def _draw_wrapped(c: canvas.Canvas, text: str, x: float, y: float, max_w: float, font: str, size: int, max_lines: int) -> int:
    if not text:
        return 0
    words = text.split()
    lines: List[str] = []
    line = ""
    for w in words:
        test = f"{line} {w}".strip()
        if stringWidth(test, font, size) <= max_w:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
        if len(lines) >= max_lines:
            break
    if line and len(lines) < max_lines:
        lines.append(line)
    c.setFont(font, size)
    for i, ln in enumerate(lines):
        c.drawString(x, y - (i * (size + 2)), ln)
    return len(lines)

def _norm_file_types(file_types: Optional[Iterable[str]]) -> List[str]:
    out = []
    for v in (file_types or []):
        s = str(v or "").strip().lower()
        if s:
            out.append(s)
    return out


def _file_abs_path(pf: PartFile) -> str:
    root = (current_app.config.get("FILE_ROOT_LOCAL") or "").strip()
    if getattr(pf, "path", None):
        return pf.path if os.path.isabs(pf.path) else os.path.join(root, pf.path)
    if getattr(pf, "rel_path", None):
        return os.path.join(root, (pf.rel_path or "").replace("/", os.sep))
    return ""


def _collect_part_files(pn: str, rev: str | None, file_types: Optional[Iterable[str]] = None) -> List[PartFile]:
    if rev is None:
        q = PartFile.objects(part_number__iexact=pn)
    else:
        q = PartFile.objects(part_number__iexact=pn, revision__iexact=(rev or ""))
    files = list(q)
    groups = set(_norm_file_types(file_types))
    if not groups:
        return files
    out = []
    for pf in files:
        group = (getattr(pf, "ext_group", None) or "").lower()
        ext = (getattr(pf, "ext", None) or "").lower()
        if group in groups or ext in groups:
            out.append(pf)
    return out


def _collect_order_parts(order: Order, include_children: bool) -> List[Tuple[str, str]]:
    parts: List[Tuple[str, str]] = []
    seen = set()

    def add(pn: str, rev: str):
        key = (pn.lower(), (rev or "").lower())
        if key in seen:
            return
        seen.add(key)
        parts.append((pn, rev))

    for line in (order.lines or []):
        pn = (line.pn or "").strip()
        if not pn:
            continue
        rev = _resolve_rev(pn, line.rev)
        add(pn, rev)
        if include_children:
            try:
                children = _flatten_bom(
                    pn,
                    rev,
                    full=True,
                    include_consumed=True,
                    terminal_processes=["welding", "purchase", "machine"],
                )
            except Exception:
                children = []
            for cpn, crev, _ in children:
                if cpn:
                    child_rev = _clean_rev(crev)
                    add(cpn, child_rev or "")
    return parts


def _merge_pdf_paths(paths: List[str]) -> Tuple[bytes, List[int]]:
    try:
        from PyPDF2 import PdfMerger, PdfReader
    except Exception:
        return b"", []
    merger = PdfMerger()
    starts: List[int] = []
    total = 1
    for p in paths:
        try:
            rdr = PdfReader(p)
            starts.append(total)
            total += len(rdr.pages)
            merger.append(p)
        except Exception:
            continue
    buf = io.BytesIO()
    merger.write(buf)
    merger.close()
    return buf.getvalue(), starts


def _merge_pdf_bytes(segments: List[bytes]) -> bytes:
    try:
        from PyPDF2 import PdfMerger
    except Exception:
        return b""
    merger = PdfMerger()
    for b in segments:
        try:
            merger.append(io.BytesIO(b))
        except Exception:
            continue
    buf = io.BytesIO()
    merger.write(buf)
    merger.close()
    return buf.getvalue()


def _order_cover_pdf(order: Order) -> Optional[bytes]:
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
    except Exception:
        return None
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    margin = 18 * mm
    y = H - margin
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin, y, f"Scope Binder: {order.order_number}")
    y -= 10 * mm
    c.setFont("Helvetica", 11)
    if order.order_date:
        c.drawString(margin, y, f"Order date: {order.order_date.strftime('%Y-%m-%d')}")
        y -= 6 * mm
    if order.supplier:
        c.drawString(margin, y, f"Supplier: {order.supplier.name}")
        y -= 6 * mm
    if order.customer:
        c.drawString(margin, y, f"Customer: {order.customer.name}")
        y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawString(margin, 20 * mm, "Generated by TinyMRP")
    c.save()
    return buf.getvalue()


def _order_index_pdf(entries: List[Tuple[str, int]], cover_pages: int) -> Optional[bytes]:
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfbase.pdfmetrics import stringWidth
        from PyPDF2 import PdfReader
    except Exception:
        return None
    if not entries:
        return None

    def _build(assumed_index_pages: int) -> bytes:
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        W, H = A4
        left_x = 18 * mm
        right_x = W - 18 * mm
        y = H - 20 * mm
        c.setFont("Helvetica-Bold", 16)
        c.drawString(left_x, y, "Index")
        y -= 10 * mm
        c.setFont("Helvetica", 10)
        dot_w = stringWidth(".", "Helvetica", 10)
        for label, start in entries:
            if y < 20 * mm:
                c.showPage()
                y = H - 20 * mm
                c.setFont("Helvetica", 10)
            page_no = cover_pages + assumed_index_pages + int(start)
            left_w = stringWidth(label, "Helvetica", 10)
            page_s = str(page_no)
            right_w = stringWidth(page_s, "Helvetica", 10)
            dots_area = max(0, right_x - (left_x + left_w) - right_w - 6)
            n_dots = int(dots_area / max(dot_w, 0.1))
            c.drawString(left_x, y, label)
            if n_dots > 0:
                c.drawString(left_x + left_w + 3, y, "." * n_dots)
            c.drawRightString(right_x, y, page_s)
            y -= 6 * mm
        c.save()
        return buf.getvalue()

    first = _build(1)
    try:
        idx_pages = len(PdfReader(io.BytesIO(first)).pages)
    except Exception:
        idx_pages = 1
    if idx_pages == 1:
        return first
    return _build(idx_pages)


def _build_order_binder(
    order: Order,
    parts: List[Tuple[str, str]],
    file_types: Optional[Iterable[str]],
) -> Optional[bytes]:
    try:
        from PyPDF2 import PdfReader
    except Exception:
        return None
    groups = set(_norm_file_types(file_types))
    allow_all = not groups
    allow_pdf = allow_all or "pdf" in groups or "datasheet" in groups
    if not allow_pdf:
        return None
    pdf_paths: List[str] = []
    entries: List[Tuple[str, str]] = []
    for pn, rev in parts:
        q = PartFile.objects(part_number__iexact=pn)
        if rev is not None:
            q = q.filter(revision__iexact=(rev or ""))
        files = list(q)
        for pf in files:
            ext = (getattr(pf, "ext", None) or "").lower()
            group = (getattr(pf, "ext_group", None) or "").lower()
            if ext != "pdf":
                continue
            if not allow_all and group not in groups and ext not in groups:
                continue
            pth = _file_abs_path(pf)
            if not pth or not os.path.isfile(pth):
                continue
            base = os.path.splitext(os.path.basename(pth))[0]
            label = f"{pn} {rev} - {base}".strip()
            pdf_paths.append(pth)
            entries.append((label, pth))

    if not pdf_paths:
        return None

    pdf_paths = [p for _, p in sorted(entries, key=lambda t: (t[0].lower(), t[1].lower()))]
    body_bytes, body_starts = _merge_pdf_paths(pdf_paths)
    if not body_bytes:
        return None

    indexed = []
    for pth, start in zip(pdf_paths, body_starts):
        base = os.path.splitext(os.path.basename(pth))[0]
        indexed.append((base, start))

    cover = _order_cover_pdf(order)
    cover_pages = 0
    if cover:
        try:
            cover_pages = len(PdfReader(io.BytesIO(cover)).pages)
        except Exception:
            cover_pages = 1
    index = _order_index_pdf(indexed, cover_pages)
    segments = []
    if cover:
        segments.append(cover)
    if index:
        segments.append(index)
    segments.append(body_bytes)
    merged = _merge_pdf_bytes(segments)
    if not merged:
        return None
    return _overlay_numbers_and_stamps(merged, [], skip_first_page=bool(cover))


def build_scope_pdf(order: Order) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    margin = 14 * mm
    y = page_h - margin

    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, f"Scope of Supply: {order.order_number}")
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawString(margin, y, f"Order type: {order.kind or 'purchase'}")
    y -= 4 * mm
    c.drawString(margin, y, f"Status: {order.status or 'draft'}")
    y -= 4 * mm
    if order.customer:
        c.drawString(margin, y, f"Customer: {order.customer.name}")
        y -= 4 * mm
    if order.supplier:
        c.drawString(margin, y, f"Supplier: {order.supplier.name}")
        y -= 4 * mm
    if order.order_date:
        c.drawString(margin, y, f"Order date: {order.order_date.strftime('%Y-%m-%d')}")
        y -= 4 * mm
    y -= 4 * mm

    col_thumb = 18 * mm
    col_pn = 38 * mm
    col_rev = 12 * mm
    col_qty = 14 * mm
    col_desc = page_w - margin * 2 - col_thumb - col_pn - col_rev - col_qty
    row_h = 12 * mm

    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y, "Thumb")
    c.drawString(margin + col_thumb, y, "Part Number")
    c.drawString(margin + col_thumb + col_pn, y, "Rev")
    c.drawString(margin + col_thumb + col_pn + col_rev, y, "Qty")
    c.drawString(margin + col_thumb + col_pn + col_rev + col_qty, y, "Description")
    y -= 6 * mm

    for line in (order.lines or []):
        if y < margin + row_h:
            c.showPage()
            y = page_h - margin

        pn = (line.pn or "").strip()
        rev = _resolve_rev(pn, line.rev or "")
        desc = (line.description or "").strip()
        if not desc:
            p = Part.objects(part_number__iexact=pn, revision__iexact=rev).first()
            desc = (p.description or "") if p else ""
        qty = float(line.qty or 0.0)

        img_path = _thumb_path(pn, rev) or _logo_path()
        try:
            if img_path and os.path.exists(img_path):
                c.drawImage(ImageReader(img_path), margin, y - 9 * mm, width=14 * mm, height=9 * mm, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

        c.setFont("Helvetica", 9)
        c.drawString(margin + col_thumb, y, pn)
        c.drawString(margin + col_thumb + col_pn, y, rev or "-")
        c.drawRightString(margin + col_thumb + col_pn + col_rev + col_qty - 2, y, f"{qty:g}")

        _draw_wrapped(c, desc, margin + col_thumb + col_pn + col_rev + col_qty, y, col_desc, "Helvetica", 8, 2)

        y -= row_h

    c.showPage()
    c.save()
    return buf.getvalue()


def build_scope_zip(
    order: Order,
    pdf_bytes: bytes,
    *,
    attach_docs: bool,
    include_children: bool,
    file_types: Optional[Iterable[str]] = None,
    include_binder: bool = False,
) -> bytes:
    buf = io.BytesIO()
    safe_order = _safe_name(order.order_number)
    pdf_name = f"{safe_order}_scope.pdf"

    missing: List[str] = []
    added = 0

    with ZipFile(buf, "w", ZIP_DEFLATED) as zf:
        zf.writestr(pdf_name, pdf_bytes)
        parts = _collect_order_parts(order, include_children)

        if include_binder:
            binder = _build_order_binder(order, parts, file_types)
            if binder:
                zf.writestr(f"{safe_order}_binder.pdf", binder)
            else:
                zf.writestr("binder_manifest.txt", "No PDF files were found for the parts in this order.\n")

        if attach_docs:
            seen = set()
            for pn, rev in parts:
                files = _collect_part_files(pn, rev, file_types=file_types)
                if not files:
                    missing.append(f"{pn},{rev}: no files found in database")
                for pf in files:
                    pth = _file_abs_path(pf)
                    if not pth or not os.path.exists(pth):
                        missing.append(f"{pn},{pf.revision or rev}: {pf.rel_path or pf.path or 'missing path'}")
                        continue
                    if pth in seen:
                        continue
                    seen.add(pth)
                    rel = pf.rel_path or os.path.basename(pth)
                    arc = os.path.join("files", pn, (pf.revision or rev or "rev"), rel.replace("\\", "/"))
                    zf.write(pth, arcname=arc)
                    added += 1

            if added == 0:
                zf.writestr("files/README.txt", "No files were found on disk for the parts in this order.\n")
            if missing:
                zf.writestr("scope_manifest.txt", "\n".join(missing))

    return buf.getvalue()
