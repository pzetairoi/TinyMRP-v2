from __future__ import annotations

from datetime import datetime
import io
import os
from typing import List
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


def _safe_name(value: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in (value or "").strip())


def _resolve_rev(pn: str, rev: str | None) -> str:
    rev = (rev or "").strip()
    if rev:
        return rev
    p = Part.objects(part_number__iexact=pn).order_by("-updated_at").first()
    if not p:
        return ""
    attrs = harvest_part_attrs(p)
    return (attrs.get("revision") or p.revision or "").strip()


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


def _collect_part_files(pn: str, rev: str) -> List[PartFile]:
    q = PartFile.objects(part_number__iexact=pn, revision__iexact=rev)
    if q.limit(1).count() == 0 and rev:
        q = PartFile.objects(part_number__iexact=pn, revision__iexact="")
    if q.limit(1).count() == 0:
        q = PartFile.objects(part_number__iexact=pn)
    return list(q)


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


def build_scope_zip(order: Order, pdf_bytes: bytes, attach_docs: bool) -> bytes:
    buf = io.BytesIO()
    root = (current_app.config.get("FILE_ROOT_LOCAL") or "").strip()
    safe_order = _safe_name(order.order_number)
    pdf_name = f"{safe_order}_scope.pdf"

    missing: List[str] = []
    added = 0

    with ZipFile(buf, "w", ZIP_DEFLATED) as zf:
        zf.writestr(pdf_name, pdf_bytes)
        if attach_docs:
            seen = set()
            for line in (order.lines or []):
                pn = (line.pn or "").strip()
                rev = _resolve_rev(pn, line.rev or "")
                files = _collect_part_files(pn, rev)
                if not files:
                    missing.append(f"{pn},{rev}: no files found in database")
                for pf in files:
                    pth = pf.path if os.path.isabs(pf.path or "") else os.path.join(root, (pf.rel_path or "").replace("/", os.sep))
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
