# app/services/import_zip.py
import ast, io, zipfile, re
from typing import Dict, Any, List, Tuple, Iterable, Set
from mongoengine import NotUniqueError
from mongoengine.queryset.visitor import Q
from app.models.part import Part
from app.models.bom import BOMLink
from app.services.thumbs_gen import generate_thumbs_for_parts
from collections import defaultdict

# Import necessary services for file scanning and upserting
from app.services.filescan import discover_part_files, upsert_part_files
# Import necessary services for attributes normalization and merging
from app.services.attrs import normalize_props, merge_save_part_attrs, process_attributes
from app.services.processmeta import normalize_processes


from flask import current_app


def _base_pn(pn: str) -> str:
    if not pn:
        return ""
    return pn.split("^", 1)[0].strip()

def _safe_qty(s: str) -> float:
    try:
        return float(s.strip()) if s and s.strip() else 1.0
    except Exception:
        return 1.0

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

def _parse_flatbom(txt: str) -> List[Dict[str, Any]]:
    """
    FLATBOM contains one Python-like dict per line with single quotes.
    We remove literal '...' sequences and ast.literal_eval each line safely.
    """
    out = []
    for raw in txt.strip().splitlines():
        if not raw.strip():
            continue
        cleaned = raw.replace("...", "")
        try:
            d = ast.literal_eval(cleaned)
            if isinstance(d, dict):
                out.append(d)
        except Exception:
            # ignore unparseable line
            pass
    return out

def _attr_ci_value(attrs: Dict[str, Any], key: str) -> List[str]:
    if not isinstance(attrs, dict):
        return []
    key_l = (key or "").strip().lower()
    hits: List[str] = []
    for k, v in attrs.items():
        try:
            if str(k or "").strip().lower() != key_l:
                continue
        except Exception:
            continue
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            hits.extend([str(x) for x in v if x is not None])
        else:
            hits.append(str(v))
    return hits

def _hardware_folder_tokens() -> List[str]:
    cfg = current_app.config.get("HARDWARE_FOLDERS") or []
    raw: List[str] = []
    if isinstance(cfg, str):
        raw = [p for p in re.split(r"[;,]", cfg) if p.strip()]
    else:
        for item in cfg:
            if item is None:
                continue
            raw.append(str(item))
    tokens: List[str] = []
    for item in raw:
        for chunk in re.split(r"[^A-Za-z0-9]+", str(item)):
            t = chunk.strip().lower()
            if not t:
                continue
            tokens.append(t)
            if t.endswith("ies") and len(t) > 3:
                tokens.append(t[:-3] + "y")
            if t.endswith("es") and len(t) > 2:
                tokens.append(t[:-2])
            if t.endswith("s") and len(t) > 1:
                tokens.append(t[:-1])
    seen: Set[str] = set()
    out: List[str] = []
    for t in tokens:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out

def _path_text_from_attrs(attrs: Dict[str, Any]) -> str:
    text_parts: List[str] = []
    for key in ("folder", "file", "filepath", "path", "nativepath", "native_file", "file_path"):
        text_parts.extend(_attr_ci_value(attrs, key))
    return " ".join(text_parts).lower()

def _is_hardware_by_folder(attrs: Dict[str, Any]) -> bool:
    tokens = _hardware_folder_tokens()
    if not tokens:
        return False
    path_text = _path_text_from_attrs(attrs)
    if not path_text:
        return False
    path_text = path_text.lower()
    words = [w for w in re.split(r"[^a-z0-9]+", path_text) if w]
    for t in tokens:
        if t in path_text:
            return True
        for w in words:
            if t in w:
                return True
    return False

def _is_hardware_by_process(attrs: Dict[str, Any]) -> bool:
    meta = current_app.config.get("PROCESS_META", {}) or {}
    try:
        procs = normalize_processes(attrs, meta)
    except Exception:
        procs = []
    return "hardware" in (p for p in procs if p)

def _normalize_part(d: Dict[str, Any]) -> Dict[str, Any]:
    low = { (k.lower() if isinstance(k,str) else k): v for k,v in d.items() }
    pn = d.get("partnumber") or low.get("part_number") or low.get("pn") or ""
    pn = _base_pn(str(pn))
    # description preference
    desc = (d.get("description") or low.get("description") or "") or ""
    for k in ("desc1","desc2","desc3","desc"):
        if k in low and low[k]:
            desc = (f"{desc} {low[k]}").strip()
    category = d.get("category") or low.get("category") or ""
    uom = d.get("uom") or d.get("UoM") or low.get("uom") or "EA"
    revision = _clean_rev(d.get("revision") or low.get("revision") or "")

    return {
        "part_number": pn,
        "description": (desc or "").strip(),
        "category": (str(category) if category is not None else "").strip(),
        "uom": (str(uom) if uom is not None else "EA").strip() or "EA",
        "revision": _clean_rev(revision),
        "attrs": d,  # store full original dict
    }

def _parse_treebom(txt: str) -> List[Tuple[str, str, str, str, float]]:
    """
    TREEBOM is a tab-separated table with headers:
      ITEM NO. | PART NUMBER | Revision | QTY.
    Item numbers like 1, 1.2, 1.2.3 denote hierarchy.

    Returns a list of (parent_pn, parent_rev, child_pn, child_rev, qty).
    """
    lines = txt.splitlines()
    rows = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        if parts[0].strip() == "ITEM NO.":
            continue
        item_no = parts[0].strip()
        part_number = parts[1].strip()
        revision = _clean_rev(parts[2].strip())
        qty = parts[3].strip()
        rows.append({"item_no": item_no, "part_number": part_number, "revision": revision, "qty": qty})

    # Map item_no -> (pn, revision) then build links
    item_to_part: Dict[str, Tuple[str, str]] = {}
    for r in rows:
        pn = _base_pn(r["part_number"])
        rev = _clean_rev(r.get("revision") or "")
        item_to_part[r["item_no"]] = (pn, rev)

    links: List[Tuple[str, str, str, str, float]] = []
    for r in rows:
        item = r["item_no"]
        child_entry = item_to_part.get(item)
        if not child_entry or item == "1":
            continue
        child_pn, child_rev = child_entry
        # find nearest ancestor with a PN
        parent_item = item.rsplit(".", 1)[0] if "." in item else ""
        while parent_item and not item_to_part.get(parent_item):
            parent_item = parent_item.rsplit(".", 1)[0] if "." in parent_item else ""
        if not parent_item:
            continue
        parent_pn, parent_rev = item_to_part[parent_item]
        if not parent_pn or parent_pn == child_pn:
            continue
        qty = _safe_qty(r["qty"])
        links.append((parent_pn, parent_rev, child_pn, child_rev, qty))
    return links

def _aggregate_links(
    links: Iterable[Tuple[str, str, str, str, float]]
) -> List[Tuple[str, str, str, str, float]]:
    totals: Dict[Tuple[str, str, str, str], float] = {}
    for parent_pn, parent_rev, child_pn, child_rev, qty in links:
        key = (
            _base_pn(str(parent_pn)).strip(),
            _clean_rev(parent_rev),
            _base_pn(str(child_pn)).strip(),
            _clean_rev(child_rev),
        )
        if not key[0] or not key[2]:
            continue
        totals[key] = totals.get(key, 0.0) + float(qty or 0.0)
    out: List[Tuple[str, str, str, str, float]] = []
    for (ppn, prev, cpn, crev), qty in totals.items():
        out.append((ppn, prev, cpn, crev, qty))
    out.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
    return out

def _ensure_part_exists(pn: str, rev: str, seed_tag: str) -> bool:
    pn = _base_pn(str(pn)).strip()
    rev = _clean_rev(rev)
    if not pn:
        return False
    if Part.objects(part_number=pn, revision=rev).first():
        return False
    try:
        Part(part_number=pn, revision=rev, description="", uom="EA", attrs={"seed": seed_tag}).save()
        return True
    except NotUniqueError:
        return False

def _find_existing_link(parent_pn: str, parent_rev: str, child_pn: str, child_rev: str):
    query = dict(parent_pn=parent_pn, child_pn=child_pn)
    if "parent_rev" in BOMLink._fields and "child_rev" in BOMLink._fields:
        query.update(parent_rev=parent_rev, child_rev=child_rev)
    existing_links = list(BOMLink.objects(**query))

    if not existing_links:
        return None, []

    existing_links.sort(key=lambda link: link.updated_at or link.id, reverse=True)
    return existing_links[0], existing_links[1:]

def _clear_existing_links(parents: Iterable[Tuple[str, str]]) -> int:
    removed = 0
    for parent_pn, parent_rev in parents:
        if not parent_pn:
            continue
        q = BOMLink.objects(parent_pn=parent_pn)
        if "parent_rev" in BOMLink._fields:
            if parent_rev:
                q = q.filter(parent_rev=parent_rev)
            else:
                q = q.filter(Q(parent_rev="") | Q(parent_rev=None) | Q(parent_rev__exists=False))
        removed += q.count()
        q.delete()
    return removed

def import_bom_zip(file_bytes: bytes, filename: str, seed_tag: str = "upload") -> Dict[str, Any]:
    """
    Main entry: import a single ZIP file.
    Creates/updates Parts from FLATBOM and links from TREEBOM.
    Stores all properties under Part.attrs.
    """
    z = zipfile.ZipFile(io.BytesIO(file_bytes))
    # find the first *_FLATBOM.txt and *_TREEBOM.txt
    flat_name = next((n for n in z.namelist() if n.endswith("_FLATBOM.txt")), None)
    tree_name = next((n for n in z.namelist() if n.endswith("_TREEBOM.txt")), None)

    created_parts = 0
    updated_parts = 0
    created_links = 0
    removed_links = 0
    skipped_links = 0
    found_artifacts = 0
    skipped_artifacts = 0
    tree_parts: Set[Tuple[str, str]] = set()
    seeded_parts: Set[Tuple[str, str]] = set()

    # 1) Parts from FLATBOM
    part_props: Dict[Tuple[str, str], Dict[str, Any]] = {}
    if flat_name:
        flat_txt = z.read(flat_name).decode("utf-8", errors="replace")
        
        for d in _parse_flatbom(flat_txt):
            norm = _normalize_part(d)
            
            pn = norm["part_number"]
            rev = _clean_rev(norm.get("revision") or "")
                        
            if pn:
                key = (pn, rev)
                # keep first occurrence to avoid duplicate inserts on repeated rows
                if key not in part_props:
                    part_props[key] = norm

    
    # Upsert parts
    for (pn, rev), norm in part_props.items():
        ##print( "upserting part", pn, rev, norm)
        rev = _clean_rev(rev)
        attrs = norm["attrs"] or {}
    
        p = Part.objects(part_number=pn, revision=rev).first()

        
        if not p:
            p = Part(part_number=pn, revision=rev)
            created_parts += 1
        else:
            updated_parts += 1
        p.description = norm["description"]
        p.category = norm["category"]
        p.uom = norm["uom"]
        
        

        # attrs = p.attrs or {}
        # print("attributes", attrs)
        attrs, processes = process_attributes(attrs)
        hardware_by_folder = _is_hardware_by_folder(attrs)
        hardware_by_process = _is_hardware_by_process(attrs)
        if hardware_by_folder or hardware_by_process:
            attrs["process"] = "hardware"
            attrs["process2"] = ""
            attrs["process3"] = ""
            attrs["processes"] = ["hardware"]
            processes = ["hardware"]
        ##print("attributes", attrs)
        ##print("processes", processes)
        
        
        # attrs.update(norm.get("attrs") or {})
        
        
        attrs["seed"] = seed_tag
        # attrs = normalize_props(attrs)
        ##print("#############################")
    
        
        
        
        p.attrs = attrs
        
        if processes:
            p.processes = processes
        
        
        try:
            p.save()
        except NotUniqueError:
            # Another process may have inserted the same part_number/revision; re-fetch and update
            existing = Part.objects(part_number=pn, revision=rev).first()
            if not existing:
                raise
            existing.description = norm["description"]
            existing.category = norm["category"]
            existing.uom = norm["uom"]
            existing.attrs = attrs
            if processes:
                existing.processes = processes
            existing.save()


    # 2) Links from TREEBOM
    if tree_name:
        tree_txt = z.read(tree_name).decode("utf-8", errors="replace")
        links = _aggregate_links(_parse_treebom(tree_txt))
        parent_pairs = {(p, _clean_rev(r)) for p, r, _, _, _ in links if p}
        if parent_pairs:
            removed_links = _clear_existing_links(parent_pairs)
        for parent_pn, parent_rev, child_pn, child_rev, qty in links:
            if not parent_pn or not child_pn:
                skipped_links += 1
                continue
            parent_rev = _clean_rev(parent_rev)
            child_rev = _clean_rev(child_rev)
            tree_parts.add((parent_pn, parent_rev))
            tree_parts.add((child_pn, child_rev))
            # ensure parts exist (create shells if missing)
            for pn, rev in ((parent_pn, parent_rev), (child_pn, child_rev)):
                if _ensure_part_exists(pn, rev, seed_tag):
                    created_parts += 1
                    seeded_parts.add((_base_pn(pn), _clean_rev(rev)))

            existing, duplicates = _find_existing_link(
                parent_pn, parent_rev, child_pn, child_rev)
            if duplicates:
                for dup in duplicates:
                    dup.delete()

            if existing:
                existing.qty = qty
                existing.uom = existing.uom or "EA"
                if hasattr(existing, "parent_rev"):
                    existing.parent_rev = parent_rev
                if hasattr(existing, "child_rev"):
                    existing.child_rev = child_rev
                existing.save()
            else:
                kwargs = dict(parent_pn=parent_pn, child_pn=child_pn, qty=qty, uom="EA")
                if "parent_rev" in BOMLink._fields:
                    kwargs["parent_rev"] = parent_rev
                if "child_rev" in BOMLink._fields:
                    kwargs["child_rev"] = child_rev
                BOMLink(**kwargs).save()
                created_links += 1
                
    # 3) Discover and register artifacts for all parts
    for pn, rev in tree_parts:
        key = (pn, rev)
        if key not in part_props:
            part_props[key] = {
                "part_number": pn,
                "description": "",
                "category": "",
                "uom": "EA",
                "revision": rev,
                "attrs": {"seed": seed_tag},
            }

    artifact_inserts = 0
    artifacts_found_by_type = defaultdict(int)
    seen = set()
   #print("part_props", part_props)
    for item, norm in part_props.items():
        pn = norm["part_number"]
        rev = _clean_rev(norm.get("revision") or "")  # allow ""
        key = (pn, rev)
       #print(key)
        if key in seen:
            continue
        seen.add(key)

        found = discover_part_files(pn, rev)
        
        
        recs = []
        for (group, is_dwg), meta in found.items():
            # meta is the dict you printed as "record {...}"
            rec = dict(meta)
            rec["ext_group"] = group  # e.g. 'png','pdf','dxf','step','edr','3mf','datasheet'
            rec["is_dwg"] = bool(is_dwg)
            recs.append(rec)
            # aggregate counters
            artifacts_found_by_type[str(group or "unknown")] += 1

       #print("upserting", len(recs), "artifacts for", pn, rev)
        artifact_inserts += upsert_part_files(recs, pn, (rev or ""))

    
    thumbs = generate_thumbs_for_parts(seen)
    
    
    
    
    # root guess for convenience (top item in TREEBOM)
    root_pn = None
    root_rev = ""
    if tree_name:
        txt = z.read(tree_name).decode("utf-8", errors="replace")
        for line in txt.splitlines():
            cols = line.split("\t")
            if len(cols) >= 2 and cols[0].strip() not in ("", "ITEM NO."):
                if cols[0].strip() == "1":
                    root_pn = _base_pn(cols[1].strip())
                break
    if root_pn:
        for (pn, rev), _norm in part_props.items():
            if pn == root_pn:
                if rev:
                    root_rev = _clean_rev(rev)
                    break
                if not root_rev:
                    root_rev = _clean_rev(rev or "")

    return {
        "zip": filename,
        "root": root_pn,
        "root_revision": root_rev,
        "parts_created": created_parts,
        "parts_updated": updated_parts,
        "links_created": created_links,
        "links_skipped": skipped_links,
        "links_removed": removed_links,
        "parts_seeded": len(seeded_parts),
        "parts_seeded_list": [{"part_number": pn, "revision": rev} for pn, rev in sorted(seeded_parts)],
        "parts_with_props": len(part_props),
        "artifacts_added": artifact_inserts,
        "artifacts_found_by_type": dict(sorted(artifacts_found_by_type.items())),
        "thumbnails_built": thumbs,
        "thumbnails_generated": thumbs
    }
