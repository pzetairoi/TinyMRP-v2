# app/services/import_zip.py
import ast, io, zipfile, re
from typing import Dict, Any, List, Tuple, Iterable
from mongoengine.queryset.visitor import Q
from app.models.part import Part
from app.models.bom import BOMLink
from app.services.thumbs_gen import generate_thumbs_for_parts

# Import necessary services for file scanning and upserting
from app.services.filescan import discover_part_files, upsert_part_files
# Import necessary services for attributes normalization and merging
from app.services.attrs import normalize_props, merge_save_part_attrs, process_attributes


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
    revision = d.get("revision") or low.get("revision") or ""

    return {
        "part_number": pn,
        "description": (desc or "").strip(),
        "category": (str(category) if category is not None else "").strip(),
        "uom": (str(uom) if uom is not None else "EA").strip() or "EA",
        "revision": (str(revision) if revision is not None else "").strip(),
        "attrs": d,  # store full original dict
    }

def _parse_treebom(txt: str) -> List[Tuple[str, str, float]]:
    """
    TREEBOM is a tab-separated table with headers:
      ITEM NO. | PART NUMBER | Revision | QTY.
    Item numbers like 1, 1.2, 1.2.3 denote hierarchy.

    Returns a list of (parent_pn, child_pn, qty).
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
        revision = parts[2].strip()
        qty = parts[3].strip()
        rows.append({"item_no": item_no, "part_number": part_number, "revision": revision, "qty": qty})

    # Map item_no → pn (base) then build links
    item_to_pn: Dict[str, str] = {}
    for r in rows:
        pn = _base_pn(r["part_number"])
        item_to_pn[r["item_no"]] = pn

    links: List[Tuple[str, str, float]] = []
    for r in rows:
        item = r["item_no"]
        child_pn = item_to_pn.get(item, "")
        if not child_pn or item == "1":
            continue
        # find nearest ancestor with a PN
        parent_item = item.rsplit(".", 1)[0] if "." in item else ""
        while parent_item and not item_to_pn.get(parent_item):
            parent_item = parent_item.rsplit(".", 1)[0] if "." in parent_item else ""
        if not parent_item:
            continue
        parent_pn = item_to_pn[parent_item]
        if not parent_pn or parent_pn == child_pn:
            continue
        qty = _safe_qty(r["qty"])
        links.append((parent_pn, child_pn, qty))
    return links

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
    skipped_links = 0
    found_artifacts = 0
    skipped_artifacts = 0

    # 1) Parts from FLATBOM
    part_props: Dict[str, Dict[str, Any]] = {}
    if flat_name:
        flat_txt = z.read(flat_name).decode("utf-8", errors="replace")
        itemcounter=0
        for d in _parse_flatbom(flat_txt):
            norm = _normalize_part(d)
            pn = norm["part_number"]
            rev=norm.get("revision") or ""
            
            print("normalized part", pn, rev, norm)
            if pn and rev:
                part_props[str(itemcounter)] = norm
                itemcounter+=1

    # Upsert parts
    for itemref, norm in part_props.items():
        print( "upserting part", itemref, norm)
        pn=norm["part_number"]
        rev=norm.get("revision") or ""        
        attrs=norm["attrs"] or {}

        
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
        # print("attributes", attrs)
        # print("processes", processes)
        
        
        # attrs.update(norm.get("attrs") or {})
        
        
        attrs["seed"] = seed_tag
        # attrs = normalize_props(attrs)
        print("#############################")
        print("attributes", attrs)
        
        
        
        p.attrs = attrs
        
        if processes:
            p.processes = processes
        
        
        p.save()


    # 2) Links from TREEBOM
    if tree_name:
        tree_txt = z.read(tree_name).decode("utf-8", errors="replace")
        links = _parse_treebom(tree_txt)
        for parent_pn, child_pn, qty in links:
            if not parent_pn or not child_pn:
                skipped_links += 1
                continue
            # ensure parts exist (create shells if missing)
            for pn in (parent_pn, child_pn):
                if not Part.objects(part_number=pn).first():
                    Part(part_number=pn, description="", uom="EA", attrs={"seed": seed_tag}).save()
                    created_parts += 1
            existing = BOMLink.objects(parent_pn=parent_pn, child_pn=child_pn).first()
            if existing:
                existing.qty = qty
                existing.uom = existing.uom or "EA"
                existing.save()
            else:
                BOMLink(parent_pn=parent_pn, child_pn=child_pn, qty=qty, uom="EA").save()
                created_links += 1
                
    # 3) Discover and register artifacts for all parts 

    artifact_inserts = 0
    seen = set()
    for pn, norm in part_props.items():
        rev = (norm.get("revision") or "")  # allow ""
        key = (pn, rev)
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
            print

        #print("upserting", len(recs), "artifacts for", pn, rev)
        artifact_inserts += upsert_part_files(recs, pn, (rev or ""))

    
    thumbs = generate_thumbs_for_parts(seen)
    



    # root guess for convenience (top item in TREEBOM)
    root_pn = None
    if tree_name:
        txt = z.read(tree_name).decode("utf-8", errors="replace")
        for line in txt.splitlines():
            cols = line.split("\t")
            if len(cols) >= 2 and cols[0].strip() not in ("", "ITEM NO."):
                if cols[0].strip() == "1":
                    root_pn = _base_pn(cols[1].strip())
                break

    return {
        "zip": filename,
        "root": root_pn,
        "parts_created": created_parts,
        "parts_updated": updated_parts,
        "links_created": created_links,
        "links_skipped": skipped_links,
        "parts_with_props": len(part_props),
        "artifacts_added": artifact_inserts,
        "thumbnails_built": thumbs
    }
