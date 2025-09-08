from __future__ import annotations
import io, os, tempfile, zipfile
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple, Set

from flask import current_app
from app.models.part import Part
from app.models.bom import BOMLink
from app.models.artifact import PartFile


@dataclass
class DocPackOptions:
    root_pn: str
    root_rev: Optional[str] = None
    depth: str = "full"                 # "top" | "full"
    include_consumed: bool = False       # placeholder (future)
    classified_filter: str = "show"      # "hide" | "show" | "only"
    processes: List[str] = None          # selected process names (canonical)
    process_mode: str = "all"            # "selected" | "all"
    file_types: List[str] = None         # ext_groups to include (e.g., ["png","pdf","step","dxf","edr","3mf","datasheet"]) 
    want_excel_bom: bool = False
    want_selected_files: bool = True
    want_pdf_binder: bool = False
    want_visual_list: bool = False
    fabrication_pack: bool = False
    binder_add_index: bool = True
    binder_add_datasheets: bool = False
    binder_page_numbers: bool = True
    # binder stamps
    stamp_quote: bool = False
    stamp_confidential: bool = False
    stamp_approved: bool = False
    stamp_wip: bool = False
    stamp_inprogress: bool = False


def _norm_rev(rev: Optional[str]) -> str:
    return (rev or "")


def _part_by(pn: str, rev: Optional[str]) -> Optional[Part]:
    rev = _norm_rev(rev)
    return Part.objects(part_number=pn, revision=rev).first() or \
           Part.objects(part_number=pn).order_by("-updated_at").first()


def _part_processes(part: Optional[Part]) -> List[str]:
    if not part:
        return []
    if isinstance(getattr(part, "processes", None), list):
        return [str(x).strip().lower() for x in (part.processes or []) if x]
    attrs = getattr(part, "attrs", {}) or {}
    procs = attrs.get("processes") or []
    if isinstance(procs, list):
        return [str(x).strip().lower() for x in procs if x]
    return []


def _flatten_bom(
    root_pn: str,
    root_rev: Optional[str],
    full: bool,
    *,
    include_consumed: bool = True,
    terminal_processes: Optional[Iterable[str]] = None,
) -> List[Tuple[str, str, float]]:
    """Return a flat list of (pn, rev, qty). If full=False, only top-level children.
    Accumulates quantities when a child appears multiple times along different paths.
    """
    root_rev = _norm_rev(root_rev)
    out: Dict[Tuple[str,str], float] = {}

    def add(pn: str, rev: str, qty: float):
        key = (pn, _norm_rev(rev))
        out[key] = out.get(key, 0.0) + float(qty or 0.0)

    terminals: Set[str] = set([str(x).strip().lower() for x in (terminal_processes or [])])

    def children(pn: str, rev: Optional[str]):
        rev = _norm_rev(rev)
        if "parent_rev" in BOMLink._fields:
            if rev is not None:
                return BOMLink.objects(parent_pn=pn, parent_rev=rev)
        return BOMLink.objects(parent_pn=pn)

    stack: List[Tuple[str,str,float]] = []
    # Seed stack with immediate children
    for l in children(root_pn, root_rev):
        stack.append((l.child_pn, getattr(l, "child_rev", "") or "", float(getattr(l, "qty", 1.0) or 1.0)))
        if not full:
            add(l.child_pn, getattr(l, "child_rev", "") or "", float(getattr(l, "qty", 1.0) or 1.0))

    if not full:
        return [(pn, rev, qty) for (pn, rev), qty in out.items()]

    while stack:
        pn, rev, q = stack.pop()
        add(pn, rev, q)
        # If we hide consumed components, stop traversing at terminal process parts
        if not include_consumed:
            pdoc = _part_by(pn, rev)
            procs = set(_part_processes(pdoc))
            if terminals and (procs & terminals):
                # do not traverse into its children
                continue
        for l in children(pn, rev):
            cq = float(getattr(l, "qty", 1.0) or 1.0) * q
            stack.append((l.child_pn, getattr(l, "child_rev", "") or "", cq))

    return [(pn, rev, qty) for (pn, rev), qty in out.items()]


def _passes_classified_filter(part: Part, mode: str) -> bool:
    mode = (mode or "show").lower()
    attrs = getattr(part, "attrs", {}) or {}
    val = str(attrs.get("classified", "")).strip().lower()
    is_classified = (val in ("yes","true","1","classified","confidential")) or (val not in ("no", "", "false", "0"))
    if mode == "hide":
        return not is_classified
    if mode == "only":
        return is_classified
    return True


def _passes_process_filter(part: Part, selected: Optional[List[str]], mode: str) -> bool:
    if (mode or "all").lower() != "selected":
        return True
    if not selected:
        return True
    procs = [p.lower() for p in (getattr(part, "processes", []) or []) if p]
    for p in selected:
        if p.lower() in procs:
            return True
    return False


def _collect_files(pn_rev_qty: Iterable[Tuple[str,str,float]], file_types: Optional[List[str]]) -> List[PartFile]:
    groups = set([g.lower() for g in (file_types or [])])
    out: List[PartFile] = []
    for pn, rev, _ in pn_rev_qty:
        q = PartFile.objects(part_number__iexact=pn)
        if rev is not None:
            q = q.filter(revision__iexact=(rev or ""))
        if groups:
            q = q.filter(ext_group__in=list(groups))
        out.extend(list(q))
    return out


def _excel_bom_bytes(flat: List[Tuple[str,str,float]]) -> bytes:
    try:
        import openpyxl
        from openpyxl.utils import get_column_letter
    except Exception:
        # Fallback: CSV in memory
        import csv
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Part Number","Revision","Qty"]) 
        for pn, rev, qty in flat:
            w.writerow([pn, rev, qty])
        return buf.getvalue().encode("utf-8")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOM"
    ws.append(["Part Number","Revision","Qty"]) 
    for pn, rev, qty in flat:
        ws.append([pn, rev, qty])
    # basic column widths
    for i, w in enumerate([24,10,8], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _visual_list_pdf(flat: List[Tuple[str,str,float]]) -> Optional[bytes]:
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
    except Exception:
        return None
    root = (current_app.config.get("FILE_ROOT_LOCAL") or "").rstrip("/\\")
    # Map (pn,rev)->first preview PNG
    rows: List[Tuple[str,str,float,str|None]] = []
    for pn, rev, qty in flat:
        q = PartFile.objects(part_number__iexact=pn, revision__iexact=(rev or ""), ext_group="png", is_dwg=False).order_by("-mtime_iso")
        path = None
        pf = q.first()
        if pf:
            path = pf.path if os.path.isabs(pf.path) else os.path.join(root, pf.rel_path.replace("/", os.sep))
            if not os.path.isfile(path):
                path = None
        rows.append((pn, rev or "", qty, path))

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    margin = 15*mm
    x_img = margin
    x_txt = x_img + 35*mm
    y = H - margin
    row_h = 32*mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, H - margin + 2*mm, "Visual List")
    c.setFont("Helvetica", 10)
    for pn, rev, qty, imgpath in rows:
        y -= row_h
        if y < margin + 20*mm:
            c.showPage(); y = H - margin
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin, H - margin + 2*mm, "Visual List")
            c.setFont("Helvetica", 10)
            y -= row_h
        # thumb
        if imgpath:
            try:
                c.drawImage(imgpath, x_img, y, width=30*mm, height=30*mm, preserveAspectRatio=True, anchor='sw', mask='auto')
            except Exception:
                pass
        # text
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x_txt, y + 24*mm, f"{pn}  REV {rev}")
        c.setFont("Helvetica", 10)
        c.drawString(x_txt, y + 18*mm, f"Qty: {qty}")
    c.save()
    return buf.getvalue()


def _overlay_numbers_and_stamps(pdf_bytes: bytes, stamps: List[str]) -> bytes:
    try:
        from reportlab.pdfgen import canvas
        from PyPDF2 import PdfReader, PdfWriter
    except Exception:
        return pdf_bytes
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    # stamp images (optional)
    stamp_files = {
        'quote': 'quote_stamp.png',
        'classified': 'classified_stamp.png',
        'approved': 'approved_stamp.png',
        'wip': 'wip_stamp.png',
        'inprogress': 'wip_stamp.png',
    }
    static_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'images')
    sel_paths = []
    for key, fn in stamp_files.items():
        if key in stamps:
            p = os.path.abspath(os.path.join(static_dir, fn))
            if os.path.isfile(p):
                sel_paths.append((key, p))

    total = len(reader.pages)
    for i, page in enumerate(reader.pages, start=1):
        mediabox = page.mediabox
        W = float(mediabox.width)
        H = float(mediabox.height)
        # build overlay for this page
        obuf = io.BytesIO()
        c = canvas.Canvas(obuf, pagesize=(W, H))
        # page number bottom-right
        c.setFont("Helvetica-Bold", 9)
        c.setFillGray(0.2)
        c.drawRightString(W - 20, 18, f"{i} / {total}")
        # stamps (semi-transparent)
        try:
            for key, spath in sel_paths:
                if key in ("approved","wip","inprogress"):
                    # center big watermark
                    c.saveState()
                    c.translate(W/2, H/2)
                    c.rotate(0)
                    c.setFillAlpha(0.13)
                    c.drawImage(spath, -W*0.25, -H*0.25, width=W*0.5, height=H*0.5, preserveAspectRatio=True, mask='auto')
                    c.restoreState()
                elif key in ("quote","classified"):
                    c.drawImage(spath, 20, H-80, width=160, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
        c.save()
        obuf.seek(0)
        # merge overlay
        from PyPDF2 import PdfReader as _PdfReader
        overlay = _PdfReader(obuf).pages[0]
        try:
            page.merge_page(overlay)
        except Exception:
            try:
                page.mergePage(overlay)  # older API
            except Exception:
                pass
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _merge_pdfs(paths: List[str]) -> Tuple[bytes, List[int]]:
    """Merge PDFs in order. Return (bytes, start_pages) where start_pages[i] is 1-based start page of doc i."""
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
            merger.append(rdr)
        except Exception:
            continue
    buf = io.BytesIO()
    merger.write(buf)
    merger.close()
    return (buf.getvalue(), starts)


def build_docpack(opts: DocPackOptions) -> Tuple[str, bytes, str]:
    """Return (filename, bytes, mime). Currently returns a ZIP by default, unless only a single PDF binder is requested.
    """
    # 1) Build BOM
    # define terminal processes for "consumed" logic
    consumed_terminals = ["welding", "purchase", "machine"]
    flat = _flatten_bom(
        opts.root_pn,
        opts.root_rev,
        full=(opts.depth != "top"),
        include_consumed=bool(opts.include_consumed),
        terminal_processes=consumed_terminals,
    )

    # 2) Filter parts by classification/process
    filtered_flat: List[Tuple[str,str,float]] = []
    # fabrication_pack convenience filters
    fab_procs = {"lasercut", "welding", "machine"}
    force_proc_filter = False
    if getattr(opts, "fabrication_pack", False):
        # restrict to fab processes
        opts.process_mode = "selected"
        opts.processes = list(sorted(fab_procs))
        force_proc_filter = True
        # restrict file types
        opts.file_types = ["dxf", "step", "pdf"]

    for pn, rev, qty in flat:
        p = Part.objects(part_number=pn, revision=(rev or "")).first() or Part.objects(part_number=pn).order_by("-updated_at").first()
        if not p:
            continue
        if not _passes_classified_filter(p, opts.classified_filter):
            continue
        if not _passes_process_filter(p, opts.processes, opts.process_mode):
            continue
        filtered_flat.append((pn, rev, qty))

    # 3) Collect files
    # include datasheets in binder if requested (affects file_types for binder only)
    chosen_files = _collect_files(filtered_flat + [(opts.root_pn, opts.root_rev or "", 1.0)], opts.file_types)
    want_zip = opts.want_selected_files or opts.want_excel_bom or opts.want_visual_list or (opts.want_pdf_binder and len(chosen_files) != 1)
    # 4) Build payloads (ZIP container)
    zip_buf = io.BytesIO()
    z: Optional[zipfile.ZipFile] = zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED)

    # Excel BOM
    if opts.want_excel_bom:
        xlsx = _excel_bom_bytes(filtered_flat)
        z.writestr("BOM.xlsx", xlsx)

    # Selected files
    if opts.want_selected_files and chosen_files:
        root = (current_app.config.get("FILE_ROOT_LOCAL") or "").rstrip("/\\")
        for f in chosen_files:
            rp = f.rel_path.replace("\\","/") if f.rel_path else os.path.basename(f.path)
            abs_path = f.path if os.path.isabs(f.path) else os.path.join(root, rp.replace("/", os.sep))
            arcname = rp
            try:
                z.write(abs_path, arcname)
            except Exception:
                continue

    # Visual list PDF
    vis_pages = 0
    if opts.want_visual_list:
        vis_pdf = _visual_list_pdf(filtered_flat)
        if vis_pdf:
            if want_zip:
                z.writestr("VisualList.pdf", vis_pdf)
            else:
                # single artifact path (rare)
                return (f"{opts.root_pn}_visual_list.pdf", vis_pdf, "application/pdf")

    # PDF binder (with index & page numbers)
    if opts.want_pdf_binder:
        # prepare list of PDFs
        binder_groups = set([g.lower() for g in (opts.file_types or [])])
        binder_files = [f for f in chosen_files if (f.ext or "").lower()=="pdf"]
        if opts.binder_add_datasheets:
            binder_files += [f for f in chosen_files if (f.ext_group or "").lower()=="datasheet" and (f.ext or "").lower()=="pdf"]
        # absolute paths
        root = (current_app.config.get("FILE_ROOT_LOCAL") or "").rstrip("/\\")
        pdf_paths = []
        for f in binder_files:
            rp = f.rel_path.replace("\\","/") if f.rel_path else os.path.basename(f.path)
            abs_path = f.path if os.path.isabs(f.path) else os.path.join(root, rp.replace("/", os.sep))
            if os.path.isfile(abs_path):
                pdf_paths.append(abs_path)
        # optional VisualList and Index as preface
        preface_bytes: List[Tuple[str, bytes]] = []
        if opts.want_visual_list:
            vis_pdf = _visual_list_pdf(filtered_flat)
            if vis_pdf:
                preface_bytes.append(("VisualList.pdf", vis_pdf))
        # first merge docs to measure page counts
        body_bytes, body_starts = _merge_pdfs(pdf_paths)
        # Count preface pages (visual list, etc.) to offset index numbers
        preface_pages = 0
        try:
            from PyPDF2 import PdfReader
            for _, b in preface_bytes:
                preface_pages += len(PdfReader(io.BytesIO(b)).pages)
        except Exception:
            pass
        # build index PDF using body_starts (+ preface)
        if opts.binder_add_index:
            try:
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.units import mm
                idx_buf = io.BytesIO()
                c = canvas.Canvas(idx_buf, pagesize=A4)
                W,H = A4
                c.setFont("Helvetica-Bold", 16)
                c.drawString(20*mm, H-20*mm, "Index")
                c.setFont("Helvetica", 10)
                y = H-30*mm
                for pth, start in zip(pdf_paths, body_starts):
                    base = os.path.basename(pth)
                    c.drawString(20*mm, y, base)
                    c.drawRightString(W-20*mm, y, str(start + preface_pages))
                    y -= 6*mm
                    if y < 20*mm:
                        c.showPage(); y = H-20*mm
                c.save()
                preface_bytes.insert(0, ("Index.pdf", idx_buf.getvalue()))
            except Exception:
                pass
        # Merge final binder: preface (visual list + index) + body
        all_segments: List[bytes] = [b for _, b in preface_bytes]
        if body_bytes:
            all_segments.append(body_bytes)
        final_pdf: bytes = b""
        if all_segments:
            # merge segments
            seg_paths = []
            tmpdir = tempfile.mkdtemp()
            try:
                for i, b in enumerate(all_segments):
                    p = os.path.join(tmpdir, f"seg_{i}.pdf")
                    with open(p, 'wb') as fh: fh.write(b)
                    seg_paths.append(p)
                merged_pdf, _ = _merge_pdfs(seg_paths)
                final_pdf = merged_pdf or b""
            finally:
                pass
        # page numbers + stamps overlay
        if opts.binder_page_numbers or any([opts.stamp_quote, opts.stamp_confidential, opts.stamp_approved, opts.stamp_wip, opts.stamp_inprogress]):
            stamps = []
            if opts.stamp_quote: stamps.append('quote')
            if opts.stamp_confidential: stamps.append('classified')
            if opts.stamp_approved: stamps.append('approved')
            if opts.stamp_wip: stamps.append('wip')
            if opts.stamp_inprogress: stamps.append('inprogress')
            if final_pdf:
                final_pdf = _overlay_numbers_and_stamps(final_pdf, stamps)
        if final_pdf:
            if want_zip:
                z.writestr("Binder.pdf", final_pdf)
            else:
                return (f"{opts.root_pn}_binder.pdf", final_pdf, "application/pdf")
    # Finish ZIP
    if z is not None:
        z.close()
    data = zip_buf.getvalue()
    name = f"{opts.root_pn}_docpack.zip"
    return (name, data, "application/zip")
