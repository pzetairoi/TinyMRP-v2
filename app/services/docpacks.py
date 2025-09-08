from __future__ import annotations
import io, os, tempfile, zipfile
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple, Set

from flask import current_app, request
from app.models.part import Part
from app.models.bom import BOMLink
from app.models.artifact import PartFile
from app.services.attrs import harvest_part_attrs, ALIASES


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


def _bom_occurrences(
    root_pn: str,
    root_rev: Optional[str],
    *,
    include_consumed: bool = True,
    terminal_processes: Optional[Iterable[str]] = None,
) -> Dict[Tuple[str,str], List[Tuple[int, float]]]:
    """Return mapping (pn,rev) -> list of (level, qty_at_that_level).
    Level starts at 1 for immediate children of the root.
    Applies the same consumed/terminal filtering as the visual list/BOM flatten.
    """
    occ: Dict[Tuple[str,str], List[Tuple[int,float]]] = {}
    terminals: Set[str] = set([str(x).strip().lower() for x in (terminal_processes or [])])

    def children(pn: str, rev: Optional[str]):
        rev = _norm_rev(rev)
        if "parent_rev" in BOMLink._fields:
            if rev is not None:
                return BOMLink.objects(parent_pn=pn, parent_rev=rev)
        return BOMLink.objects(parent_pn=pn)

    stack: List[Tuple[str,str,int,float]] = []
    for l in children(root_pn, root_rev):
        stack.append((l.child_pn, getattr(l, "child_rev", "") or "", 1, float(getattr(l, "qty", 1.0) or 1.0)))

    while stack:
        pn, rev, level, q = stack.pop()
        key = (pn, _norm_rev(rev))
        occ.setdefault(key, []).append((level, q))
        if not include_consumed:
            pdoc = _part_by(pn, rev)
            procs = set(_part_processes(pdoc))
            if terminals and (procs & terminals):
                # stop at consumed parts
                continue
        for l in children(pn, rev):
            cq = float(getattr(l, "qty", 1.0) or 1.0) * q
            stack.append((l.child_pn, getattr(l, "child_rev", "") or "", level+1, cq))
    return occ


def _excel_bom_bytes(
    root_pn: str,
    root_rev: Optional[str],
    flat: List[Tuple[str,str,float]],
    occ: Dict[Tuple[str,str], List[Tuple[int,float]]]
) -> bytes:
    try:
        import openpyxl
        from openpyxl.utils import get_column_letter
        from openpyxl.drawing.image import Image as XLImage
        from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, TwoCellAnchor
        from openpyxl.styles import Alignment, Font, PatternFill
        import json as _json
        import datetime as _dt
    except Exception:
        # Fallback: CSV in memory
        import csv
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Part Number","Revision","Qty","Levels","Level Qtys"]) 
        for pn, rev, qty in flat:
            lvls = ", ".join(str(l) for l,_ in occ.get((pn,_norm_rev(rev)), []))
            lq   = ", ".join(f"{q:g}" for _,q in occ.get((pn,_norm_rev(rev)), []))
            w.writerow([pn, rev, qty, lvls, lq])
        return buf.getvalue().encode("utf-8")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"BOM_{(root_pn or 'root')[:20]}"

    # Determine union of attribute keys (canonicalized using ALIASES on existing keys only)
    attr_keys: Set[str] = set()
    parts_cache: Dict[Tuple[str,str], Optional[Part]] = {}
    for pn, rev, _ in flat:
        key = (pn, _norm_rev(rev))
        if key not in parts_cache:
            parts_cache[key] = _part_by(pn, rev)
        p = parts_cache[key]
        if p and isinstance(getattr(p, 'attrs', None), dict):
            for k in (p.attrs or {}).keys():
                if not k:
                    continue
                kl = str(k).strip().lower()
                canon = ALIASES.get(kl, kl)
                if canon:
                    attr_keys.add(str(canon))
    # Primary columns enforced (exact names per request)
    qty_col = 'total qty (full BOM)'
    header_main = [
        'thumbnail',
        'partnumber','revision','description','approvedby','material','process','finish','mass',
        'link','oem','oem partnumber',
        qty_col,'level','level qty'
    ]
    # Remove any attribute keys that collide with primary names (case-insensitive)
    ignore = set([h.lower() for h in header_main] + ['oem_partnumber','oem partnumber'])
    header_attrs = sorted([k for k in attr_keys if k and k.lower() not in ignore])
    header = header_main + header_attrs
    ws.append(header)
    ws.freeze_panes = 'A2'

    # Column widths
    widths = {
        'thumbnail': 14,
        'partnumber': 26,
        'revision': 10,
        qty_col: 14,
        'level': 10,
        'level qty': 14,
        'description': 40,
        'approvedby': 18,
        'material': 18,
        'process': 18,
        'thickness': 12,
        'finish': 16,
        'mass': 12,
        'link': 30,
        'oem': 18,
        'oem partnumber': 22,
    }
    for i, col in enumerate(header, start=1):
        ws.column_dimensions[get_column_letter(i)].width = widths.get(col, 16)

    # Map header name -> column index for robust addressing
    header_index: Dict[str, int] = { name: idx+1 for idx, name in enumerate(header) }

    # Helper to find preview PNG path
    file_root = (current_app.config.get('FILE_ROOT_LOCAL') or '').rstrip('/\\')
    fallback_logo = _static_image_path('tinylogo.png')
    def preview_png_path(pn: str, rev: str) -> Optional[str]:
        q = PartFile.objects(part_number__iexact=pn, revision__iexact=_norm_rev(rev), ext_group='png', is_dwg=False).order_by('-mtime_iso')
        pf = q.first()
        if pf:
            pth = pf.path if os.path.isabs(pf.path) else os.path.join(file_root, pf.rel_path.replace('/', os.sep))
            if os.path.isfile(pth):
                return pth
        return fallback_logo

    # helper to coerce any value into an Excel-friendly scalar
    def _cell(v):
        if v is None:
            return ""
        if isinstance(v, (list, tuple, set)):
            return ", ".join(str(x) for x in v)
        # allow datetime/date as-is
        try:
            import datetime as __dt
            if isinstance(v, (__dt.date, __dt.datetime)):
                return v
        except Exception:
            pass
        if isinstance(v, dict):
            try:
                return _json.dumps(v, ensure_ascii=False)
            except Exception:
                return str(v)
        # keep numbers/bools
        if isinstance(v, (int, float, bool)):
            return v
        return str(v)

    # Write rows
    row_idx = 1
    for pn, rev, qty in flat:
        row_idx += 1
        key = (pn, _norm_rev(rev))
        p = parts_cache.get(key)
        # Normalize attributes to handle mixed-case and aliases (e.g., Link/LINK/oem_link -> link)
        attrs = harvest_part_attrs(p) if p else {}
        levels_list = [l for l,_ in occ.get(key, [])]
        qtys_list = [q for _,q in occ.get(key, [])]
        # processes as comma-separated
        proc_list = []
        if p and isinstance(getattr(p, 'processes', None), list):
            proc_list = [str(x) for x in p.processes if x]
        elif isinstance(attrs.get('processes'), list):
            proc_list = [str(x) for x in attrs.get('processes') if x]
        else:
            for k in ('process','process2','secondprocess','process3','thirdprocess'):
                if attrs.get(k): proc_list.append(str(attrs.get(k)))

        values = {
            'thumbnail': '',
            'partnumber': pn,
            'revision': _norm_rev(rev),
            'description': getattr(p, 'description', '') or attrs.get('description','') or '',
            'approvedby': attrs.get('approvedby','') or attrs.get('approved_by',''),
            'material': attrs.get('material',''),
            'process': ", ".join(proc_list),
            'finish': attrs.get('finish',''),
            'mass': attrs.get('mass',''),
            'link': attrs.get('link',''),
            'oem': attrs.get('oem','') or attrs.get('manufacturer',''),
            'oem partnumber': attrs.get('oem_partnumber',''),
            qty_col: qty,
            'level': ", ".join(str(x) for x in levels_list),
            'level qty': ", ".join(f"{x:g}" for x in qtys_list),
        }
        # Merge all attributes at the end, blanks when missing
        for k in header_attrs:
            values[k] = attrs.get(k, '')
        row = [_cell(values.get(k, '')) for k in header]
        ws.append(row)
        # Adjust row height for thumbnail
        ws.row_dimensions[row_idx].height = 56
        # Add image if we have a path
        img_path = preview_png_path(pn, _norm_rev(rev))
        if img_path and os.path.isfile(img_path):
            try:
                img = XLImage(img_path)
                img.height = 48
                img.width = 48
                # Anchor to the 'thumbnail' cell (A{row}) using TwoCellAnchor so it moves/sizes with cell
                # openpyxl uses 0-based indices for AnchorMarker
                r0 = row_idx - 1
                img.anchor = TwoCellAnchor(
                    _from=AnchorMarker(col=0, colOff=5_000, row=r0, rowOff=5_000),
                    to=AnchorMarker(col=0, colOff=500_000, row=r0+1, rowOff=0),
                    editAs='twoCell'
                )
                ws.add_image(img)
            except Exception:
                pass
        # Hyperlink partnumber to the app part-detail page
        try:
            app_url = _part_detail_url(pn, _norm_rev(rev))
            pn_col = header_index.get('partnumber') or (header.index('partnumber') + 1)
            pcell = ws.cell(row=row_idx, column=pn_col)
            pcell.hyperlink = app_url
            pcell.font = Font(color='0000EE', underline='single')
        except Exception:
            pass

        # Hyperlink on link column if URL present (external only)
        try:
            raw = (values.get('link') or '').strip()
            if raw:
                url = raw
                if not (url.startswith('http://') or url.startswith('https://')):
                    url = 'http://' + url
                # Force the link into column J (10)
                lcell = ws.cell(row=row_idx, column=10)
                # HYPERLINK formula for compatibility
                disp = raw
                lcell.value = f'=HYPERLINK("{url}","{disp}")'
                try:
                    lcell.hyperlink = url
                except Exception:
                    pass
                lcell.font = Font(color='0000EE', underline='single')
        except Exception:
            pass

    # Header style & autofilter
    bold = Font(b=True)
    center = Alignment(horizontal='center')
    main_fill = PatternFill(fill_type='solid', fgColor='000000')
    main_font = Font(b=True, color='FFFFFF')
    for col_idx in range(1, len(header)+1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = bold
        cell.alignment = center
        if col_idx <= len(header_main):
            cell.fill = main_fill
            cell.font = main_font
    ws.auto_filter.ref = f"A1:{get_column_letter(len(header))}{row_idx}"

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _part_detail_url(pn: str, rev: str) -> str:
    try:
        root = (request.url_root or "").rstrip("/")  # prefers outer URL
    except Exception:
        root = ""
    if not root:
        root = (current_app.config.get("VITE_BACKEND_URL") or "http://localhost:5000").rstrip("/")
    return f"{root}/ui/part/{pn}?rev={rev}"


def _pil_to_rl_image(pil_img, width=None, height=None):
    from reportlab.lib.utils import ImageReader
    return ImageReader(pil_img)


def _process_color_map() -> Dict[str, Tuple[float,float,float]]:
    meta = current_app.config.get("PROCESS_META", {}) or {}
    out: Dict[str, Tuple[float,float,float]] = {}
    for k, v in meta.items():
        if k.startswith("_"): continue
        try:
            r, g, b = [int(x.strip()) for x in (v.get("color") or "").split(",")[:3]]
            out[k.lower()] = (max(0,min(r,255))/255.0, max(0,min(g,255))/255.0, max(0,min(b,255))/255.0)
        except Exception:
            pass
    return out


def _static_image_path(*names: str) -> Optional[str]:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'images'))
    for n in names:
        p = os.path.join(base, n)
        if os.path.isfile(p):
            return p
    return None


def _draw_svg_or_png(c, x, y, w, h, svg_name: str, png_fallback: str):
    svg_path = _static_image_path(svg_name)
    if svg_path:
        try:
            from svglib.svglib import svg2rlg
            from reportlab.graphics import renderPDF
            drawing = svg2rlg(svg_path)
            sx = w / float(drawing.width or 1)
            sy = h / float(drawing.height or 1)
            s = min(sx, sy)
            c.saveState(); c.translate(x, y); c.scale(s, s)
            renderPDF.draw(drawing, c, 0, 0)
            c.restoreState(); return
        except Exception:
            pass
    png = _static_image_path(png_fallback)
    if png:
        try:
            c.drawImage(png, x, y, width=w, height=h, preserveAspectRatio=True, anchor='sw', mask='auto')
        except Exception:
            pass


def _visual_list_pdf(flat: List[Tuple[str,str,float]], root_pn: Optional[str] = None, root_rev: Optional[str] = None) -> Optional[bytes]:
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        import qrcode
        from PIL import Image as PILImage
    except Exception:
        return None
    root = (current_app.config.get("FILE_ROOT_LOCAL") or "").rstrip("/\\")
    # Build rows with: pn, rev, qty, imgpath
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

    # Layout close to legacy BoxyGrid (3 columns on A4 portrait)
    box_w = 58*mm
    box_h = 46*mm
    gap = 6*mm
    margin = 14*mm
    W, H = A4
    cols = max(1, int((W - 2*margin + gap) // (box_w + gap)))
    # Aim for exactly 3 columns if space permits
    cols = min(max(cols, 3), 4)
    x0 = margin
    y0 = H - margin

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    # Title with root PN/REV and description, plus logos
    root_desc = ''
    if root_pn:
        try:
            rpdoc = _part_by(root_pn, root_rev or "")
            root_desc = getattr(rpdoc, 'description', '') or ''
        except Exception:
            pass
    def header():
        title = (f"{root_pn or ''} REV {root_rev or ''}").strip()
        c.setFont("Helvetica-Bold", 18)
        if title:
            c.drawCentredString(W/2, H - margin + 6*mm, title)
        if root_desc:
            c.setFont("Helvetica", 12)
            c.drawCentredString(W/2, H - margin - 1*mm, root_desc[:150])
        # top-left logo (10mm)
        _draw_svg_or_png(c, margin-8*mm, H - margin + 0.5*mm, 10*mm, 10*mm, 'logo.svg', 'tinylogo.png')
        # bottom center footer
        _draw_svg_or_png(c, W/2 - 8*mm, margin/3, 16*mm, 6*mm, 'tinyfooter.svg', 'tinyfooter.png')

    header()

    proc_colors = _process_color_map()
    rows_per_page = max(1, int((H - 2*margin + gap) // (box_h + gap)))
    cur_page = 0

    def draw_cell(ix: int, pn: str, rev: str, qty: float, imgpath: Optional[str], desc: str = ""):
        nonlocal cur_page
        page_no = ix // (cols * rows_per_page)
        if page_no != cur_page:
            c.showPage(); header(); cur_page = page_no
        pos = ix % (cols * rows_per_page)
        col = pos % cols
        row_in_page = pos // cols
        # compute origin of the cell (top-left)
        x = x0 + col * (box_w + gap)
        y = y0 - (row_in_page + 1) * (box_h + gap)
        # base box
        c.setStrokeGray(0.8); c.setLineWidth(0.7)
        c.setFillColorRGB(1,1,1)
        c.rect(x, y, box_w, box_h, stroke=1, fill=1)
        # process colored rings inside the border
        pdoc = _part_by(pn, rev)
        procs = _part_processes(pdoc)
        inset = 0.8*mm
        for i, p in enumerate(procs):
            col = proc_colors.get(p.lower())
            if not col: continue
            off = (i+1) * inset
            c.setStrokeColorRGB(*col); c.setLineWidth(2)
            c.rect(x+off, y+off, box_w-2*off, box_h-2*off, stroke=1, fill=0)
        # geometry: reserve top header (PN/REV/QTY) and bottom (desc + QR)
        top_space = 18*mm
        bottom_space = 18*mm
        # image area (left side), vertically between top_space and bottom_space
        ix_x = x + 3*mm
        ix_y = y + bottom_space
        ix_w = 30*mm
        ix_h = box_h - (top_space + bottom_space)
        if imgpath:
            try:
                c.drawImage(imgpath, ix_x, ix_y, width=ix_w, height=ix_h, preserveAspectRatio=True, anchor='sw', mask='auto')
            except Exception:
                pass
        else:
            _draw_svg_or_png(c, ix_x, ix_y, ix_w, ix_h, 'tinylogo.svg', 'tinylogo.png')
        # text area
        # Top-left header: PN and REV (left-justified)
        hl_x = x + 4*mm
        hl_y = y + box_h - 6*mm
        c.setFillGray(0.1)
        c.setFont("Helvetica-Bold", 11.5)
        c.drawString(hl_x, hl_y, f"{pn}")
        c.setFont("Helvetica", 9.5); c.setFillGray(0.25)
        c.drawString(hl_x, hl_y - 12, f"REV: {rev}")
        # Qty at top-right in bold red, same size as PN
        try:
            from reportlab.pdfbase.pdfmetrics import stringWidth
            qty_str = f"x{qty:g}" if isinstance(qty, float) else f"x{qty}"
            c.setFont("Helvetica-Bold", 11.5)
            c.setFillColorRGB(0.82, 0.0, 0.0)
            tw = stringWidth(qty_str, "Helvetica-Bold", 11.5)
            c.drawString(x + box_w - 4*mm - tw, hl_y, qty_str)
            c.setFillGray(0.1)  # restore default dark text color
        except Exception:
            pass
        # Description at bottom-left of box (avoid image/QR overlap)
        if not desc and pdoc is not None:
            try:
                desc = (getattr(pdoc, 'attrs', {}) or {}).get('description') or ''
            except Exception:
                desc = ''
        if desc:
            d_x = x + 4*mm
            d_y1 = y + 8*mm   # first line above bottom
            line_h = 9.5
            right_reserved = 18*mm + 6*mm  # QR + margin
            max_w = max(20*mm, (x + box_w) - d_x - right_reserved)
            try:
                from reportlab.pdfbase.pdfmetrics import stringWidth
                c.setFillGray(0.35); c.setFont("Helvetica", 8.8)
                words = desc.split(); lines=[]; cur=''
                for w in words:
                    t=(cur+' '+w).strip()
                    if stringWidth(t, "Helvetica", 8.8) <= max_w: cur=t
                    else:
                        if cur: lines.append(cur); cur=w
                        if len(lines)>=2: break
                if cur and len(lines)<2: lines.append(cur)
                # draw from bottom upwards to keep inside area
                if len(lines)>=1:
                    c.drawString(d_x, d_y1, lines[0])
                if len(lines)>=2:
                    c.drawString(d_x, d_y1 + line_h, lines[1])
            except Exception:
                pass
        # QR code (links to part detail) — draw last to ensure it sits on top
        try:
            qr_url = _part_detail_url(pn, rev)
            qr = qrcode.QRCode(border=0, box_size=2)
            qr.add_data(qr_url)
            qr.make(fit=True)
            qimg = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            from reportlab.lib.utils import ImageReader
            qbuf = io.BytesIO(); qimg.save(qbuf, format='PNG'); qbuf.seek(0)
            qr_size = 18*mm
            c.drawImage(ImageReader(qbuf), x + box_w - qr_size - 4*mm, y + 4*mm, width=qr_size, height=qr_size, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

        # Approval status icon (above the QR)
        try:
            approved = False
            if pdoc is not None:
                a = (getattr(pdoc, 'attrs', {}) or {})
                approved = bool((a.get('approvedby') or a.get('approved_by') or '').strip())
            icon_w = 12*mm
            icon_h = 10*mm
            icon_x = x + box_w - icon_w - 4*mm
            icon_y = y + 4*mm + qr_size + 2*mm
            if approved:
                _draw_svg_or_png(c, icon_x, icon_y, icon_w, icon_h, 'approved.svg', 'approved.png')
            else:
                _draw_svg_or_png(c, icon_x, icon_y, icon_w, icon_h, 'notapproved.svg', 'notapproved.png')
        except Exception:
            pass

    for i, (pn, rev, qty, ip) in enumerate(rows):
        try:
            pdoc = _part_by(pn, rev)
            desc = (getattr(pdoc, 'description', '') or '')
        except Exception:
            desc = ''
        draw_cell(i, pn, rev, qty, ip, desc)

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
        occ_map = _bom_occurrences(opts.root_pn, opts.root_rev, include_consumed=bool(opts.include_consumed), terminal_processes=["welding","purchase","machine"])
        xlsx = _excel_bom_bytes(opts.root_pn, opts.root_rev, filtered_flat, occ_map)
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
        vis_pdf = _visual_list_pdf(filtered_flat, opts.root_pn, opts.root_rev)
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
            vis_pdf = _visual_list_pdf(filtered_flat, opts.root_pn, opts.root_rev)
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
