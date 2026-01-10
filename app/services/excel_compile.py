from __future__ import annotations

import csv
import io
import os
import zipfile
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from app.models.part import Part
from app.models.artifact import PartFile


@dataclass
class CompileRow:
    part_number: str
    revision: str
    qty: float
    status: str  # "ok" | "missing"


def _clean_rev(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in ("nan", "none"):
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    return text.strip()


def _to_qty(value: object) -> float:
    if value is None or str(value).strip() == "":
        return 1.0
    try:
        return float(value)
    except Exception:
        return 1.0


def parse_compile_excel(path: str) -> List[CompileRow]:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    sheet = None
    for name in wb.sheetnames:
        if name.strip().lower() == "compile":
            sheet = wb[name]
            break
    if sheet is None:
        sheet = wb.active

    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []

    header = [str(c or "").strip().lower() for c in rows[0]]
    def find_col(names: Iterable[str]) -> Optional[int]:
        for name in names:
            if name in header:
                return header.index(name)
        return None

    idx_pn = find_col(["partnumber", "part number", "part_number", "pn"])
    idx_rev = find_col(["revision", "rev"])
    idx_qty = find_col(["qty", "quantity"])

    if idx_pn is None:
        return []

    out: List[CompileRow] = []
    for row in rows[1:]:
        if row is None:
            continue
        pn = str(row[idx_pn] or "").strip()
        if not pn:
            continue
        rev = _clean_rev(row[idx_rev]) if idx_rev is not None else ""
        qty = _to_qty(row[idx_qty]) if idx_qty is not None else 1.0
        out.append(CompileRow(part_number=pn, revision=rev, qty=qty, status="ok"))
    return out


def build_excel_compile_zip(
    rows: List[CompileRow],
    *,
    input_filename: str,
    input_bytes: bytes,
    file_root: str,
    file_groups: Optional[List[str]] = None,
) -> Tuple[bytes, List[CompileRow]]:
    file_groups = file_groups or ["pdf", "dxf", "step", "datasheet"]
    missing: List[CompileRow] = []
    parts: List[Tuple[str, str, float]] = []

    for r in rows:
        part = Part.objects(part_number=r.part_number, revision=r.revision).first()
        if not part:
            part = Part.objects(part_number=r.part_number).order_by("-updated_at").first()
            if part:
                r.revision = part.revision or ""
        if not part:
            r.status = "missing"
            missing.append(r)
            continue
        parts.append((part.part_number, part.revision or "", r.qty))

    buf = io.BytesIO()
    z = zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED)
    z.writestr("input.xlsx", input_bytes)

    # Summary CSV
    csv_buf = io.StringIO()
    w = csv.writer(csv_buf)
    w.writerow(["part_number", "revision", "qty", "status"])
    for r in rows:
        w.writerow([r.part_number, r.revision, f"{r.qty:g}", r.status])
    z.writestr("parts.csv", csv_buf.getvalue())

    if missing:
        msg = "\n".join(f"{r.part_number}\t{r.revision}" for r in missing)
        z.writestr("missing_parts.txt", msg)

    # Visual list (optional; skips on failures)
    try:
        from app.services.docpacks import _visual_list_pdf
        vis = _visual_list_pdf(parts, None, None)
        if vis:
            z.writestr("VisualList.pdf", vis)
    except Exception:
        pass

    # Collect files
    file_root = (file_root or "").rstrip("/\\")
    seen: Dict[str, int] = {}
    for pn, rev, _ in parts:
        qs = PartFile.objects(part_number__iexact=pn)
        if rev is not None:
            qs = qs.filter(revision__iexact=(rev or ""))
        qs = qs.filter(ext_group__in=file_groups)
        for f in qs:
            rel = f.rel_path.replace("\\", "/") if f.rel_path else ""
            abs_path = f.path if os.path.isabs(f.path) else os.path.join(file_root, rel.replace("/", os.sep))
            if not os.path.isfile(abs_path):
                continue
            base = os.path.basename(rel or abs_path)
            arc_folder = (f.ext_group or "files").lower()
            arcname = f"{arc_folder}/{base}"
            if arcname in seen:
                seen[arcname] += 1
                stem, ext = os.path.splitext(base)
                arcname = f"{arc_folder}/{stem}_{seen[arcname]}{ext}"
            else:
                seen[arcname] = 0
            z.write(abs_path, arcname)

    z.close()
    return buf.getvalue(), missing
