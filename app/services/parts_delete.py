# app/services/parts_delete.py — part deletion (DB refs + optional physical files)
from __future__ import annotations

import os
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Tuple

from app.models.part import Part
from app.models.artifact import PartFile
from app.models.bom import BOMLink
from app.models.job import Job
from app.models.order import Order
from app.models.part_revision import PartRevisionHistory
from app.services.biz_utils import calculate_order_totals
from app.services.part_norm import clean_rev
from app.services.timezone_utils import utc_now


def _match_pn_rev(pn: str, rev: str, target_pn: str, target_rev: str) -> bool:
    return (pn or "").strip().lower() == target_pn and clean_rev(rev).lower() == target_rev


def _path_is_under(abs_path: str, base_root: str) -> bool:
    try:
        ap = os.path.normcase(os.path.abspath(abs_path))
        base = os.path.normcase(os.path.abspath(base_root))
        try:
            return os.path.commonpath([ap, base]) == base
        except Exception:
            return ap.startswith(base)
    except Exception:
        return False


def _remove_existing(candidates: List[str], allowed_roots: List[str]) -> int:
    """
    Remove every candidate path that exists and lives under one of the allowed
    roots. Returns number of files actually removed. Best-effort: errors on a
    single file never abort the deletion of the record.
    """
    removed = 0
    seen: set[str] = set()
    for cand in candidates:
        if not cand:
            continue
        key = os.path.normcase(os.path.abspath(cand))
        if key in seen:
            continue
        seen.add(key)
        if not any(_path_is_under(cand, root) for root in allowed_roots if root):
            continue
        try:
            if os.path.isfile(cand):
                os.remove(cand)
                removed += 1
        except Exception:
            pass
    return removed


def _delete_physical_files_for(pn: str, rev: str) -> Dict[str, int]:
    """
    Physically remove from the server every file related to (pn, rev):
    scanned/uploaded artifacts (PartFile), their generated thumbnails, and
    associated extra files (PartExtraFile, records included).

    Only paths inside the configured storage roots are ever touched.
    """
    counts = {
        "deleted_physical_files": 0,
        "deleted_thumb_files": 0,
        "deleted_extra_files": 0,
        "deleted_extra_records": 0,
    }

    source_roots: List[str] = []
    try:
        from app.services.filescan import _sources

        for src in _sources(None):
            root = str(src.get("local_root") or "").strip()
            if root:
                source_roots.append(root)
    except Exception:
        pass

    file_root_local = ""
    try:
        from flask import current_app, has_app_context

        if has_app_context():
            file_root_local = str(
                current_app.config.get("FILE_ROOT_LOCAL")
                or current_app.config.get("FILES_LOCAL_ROOT")
                or ""
            ).strip()
    except Exception:
        file_root_local = ""

    allowed_roots = list(source_roots)
    if file_root_local:
        allowed_roots.append(file_root_local)

    if allowed_roots:
        for doc in PartFile.objects(part_number__iexact=pn, revision__iexact=rev):
            candidates: List[str] = []
            abs_path = str(getattr(doc, "path", "") or "").strip()
            if abs_path and os.path.isabs(abs_path):
                candidates.append(abs_path)
            rel = str(getattr(doc, "rel_path", "") or "").strip().replace("\\", "/").lstrip("/")
            if rel:
                for root in source_roots or ([file_root_local] if file_root_local else []):
                    candidates.append(os.path.join(root, rel.replace("/", os.sep)))
            counts["deleted_physical_files"] += _remove_existing(candidates, allowed_roots)

            thumb_rel = str(getattr(doc, "thumb_rel_path", "") or "").strip()
            if thumb_rel and file_root_local:
                thumb_abs = os.path.join(file_root_local, thumb_rel.replace("/", os.sep))
                counts["deleted_thumb_files"] += _remove_existing([thumb_abs], [file_root_local])

    try:
        from app.models.extra_file import PartExtraFile
        from app.services.extra_files import extra_abs_path, extra_root

        base_root = ""
        try:
            base_root = extra_root()
        except Exception:
            base_root = ""
        for ef in PartExtraFile.objects(part_number__iexact=pn, revision__iexact=rev):
            rel_path = str(getattr(ef, "rel_path", "") or "").strip()
            if rel_path and base_root:
                try:
                    abs_extra = extra_abs_path(rel_path)
                except Exception:
                    abs_extra = ""
                if abs_extra:
                    counts["deleted_extra_files"] += _remove_existing([abs_extra], [base_root])
            ef.delete()
            counts["deleted_extra_records"] += 1
    except Exception:
        pass

    return counts


def delete_part_and_refs(pn: str, rev: str | None, *, delete_files: bool = False) -> Dict[str, int]:
    pn_clean = (pn or "").strip()
    rev_clean = clean_rev(rev)
    if not pn_clean:
        return {
            "deleted_parts": 0,
            "deleted_files": 0,
            "deleted_bom_links": 0,
            "deleted_revisions": 0,
            "updated_jobs": 0,
            "updated_orders": 0,
            "deleted_physical_files": 0,
            "deleted_thumb_files": 0,
            "deleted_extra_files": 0,
            "deleted_extra_records": 0,
            "deleted_drawing_markups": 0,
        }

    physical = {
        "deleted_physical_files": 0,
        "deleted_thumb_files": 0,
        "deleted_extra_files": 0,
        "deleted_extra_records": 0,
    }
    if delete_files:
        try:
            physical = _delete_physical_files_for(pn_clean, rev_clean)
        except Exception:
            pass

    deleted_drawing_markups = 0
    try:
        from app.services.part_drawing_markups import delete_markups_for_part

        deleted_drawing_markups = delete_markups_for_part(pn_clean, rev_clean)
    except Exception:
        deleted_drawing_markups = 0

    deleted_parts = Part.objects(
        part_number__iexact=pn_clean,
        revision__iexact=rev_clean,
    ).delete()

    deleted_files = PartFile.objects(
        part_number__iexact=pn_clean,
        revision__iexact=rev_clean,
    ).delete()

    deleted_revisions = PartRevisionHistory.objects(
        part_number__iexact=pn_clean,
        revision__iexact=rev_clean,
    ).delete()

    parent_q = BOMLink.objects(parent_pn__iexact=pn_clean, parent_rev__iexact=rev_clean)
    child_q = BOMLink.objects(child_pn__iexact=pn_clean, child_rev__iexact=rev_clean)
    deleted_bom_links = parent_q.delete() + child_q.delete()

    target_pn = pn_clean.lower()
    target_rev = rev_clean.lower()

    updated_jobs = 0
    for job in Job.objects(bom__pn__iexact=pn_clean):
        before = len(job.bom or [])
        job.bom = [
            l for l in (job.bom or [])
            if not _match_pn_rev(l.pn or "", l.rev or "", target_pn, target_rev)
        ]
        if len(job.bom) != before:
            job.updated_at = utc_now()
            job.save()
            updated_jobs += 1

    updated_orders = 0
    for order in Order.objects(lines__pn__iexact=pn_clean):
        before = len(order.lines or [])
        order.lines = [
            l for l in (order.lines or [])
            if not _match_pn_rev(l.pn or "", l.rev or "", target_pn, target_rev)
        ]
        if len(order.lines) != before:
            subtotal, tax_amount, discount_amount = calculate_order_totals(order.lines or [])
            order.subtotal = subtotal
            order.tax_amount = tax_amount
            order.discount_amount = discount_amount
            order.total = max(subtotal - discount_amount, 0.0) + tax_amount + float(order.shipping_cost or 0.0)
            order.updated_at = utc_now()
            order.save()
            updated_orders += 1

    return {
        "deleted_parts": int(deleted_parts or 0),
        "deleted_files": int(deleted_files or 0),
        "deleted_bom_links": int(deleted_bom_links or 0),
        "deleted_revisions": int(deleted_revisions or 0),
        "updated_jobs": int(updated_jobs or 0),
        "updated_orders": int(updated_orders or 0),
        "deleted_physical_files": int(physical.get("deleted_physical_files") or 0),
        "deleted_thumb_files": int(physical.get("deleted_thumb_files") or 0),
        "deleted_extra_files": int(physical.get("deleted_extra_files") or 0),
        "deleted_extra_records": int(physical.get("deleted_extra_records") or 0),
        "deleted_drawing_markups": int(deleted_drawing_markups or 0),
    }


def _collect_bom_descendants(pn: str, rev: str) -> tuple[tuple[str, str], dict[tuple[str, str], tuple[str, str]]]:
    pn_clean = (pn or "").strip()
    rev_clean = clean_rev(rev)
    root_key = (pn_clean.lower(), rev_clean.lower())
    key_to_pair: dict[tuple[str, str], tuple[str, str]] = {root_key: (pn_clean, rev_clean)}
    queue: deque[tuple[str, str]] = deque([(pn_clean, rev_clean)])
    while queue:
        parent_pn, parent_rev = queue.popleft()
        q = BOMLink.objects(parent_pn__iexact=parent_pn, parent_rev__iexact=parent_rev).only("child_pn", "child_rev")
        for link in q:
            child_pn = (getattr(link, "child_pn", None) or "").strip()
            if not child_pn:
                continue
            child_rev = clean_rev(getattr(link, "child_rev", None) or "")
            child_key = (child_pn.lower(), child_rev.lower())
            if child_key in key_to_pair:
                continue
            key_to_pair[child_key] = (child_pn, child_rev)
            queue.append((child_pn, child_rev))
    return root_key, key_to_pair


def _safe_deletable_subtree(root_key: tuple[str, str], key_to_pair: dict[tuple[str, str], tuple[str, str]]) -> set[tuple[str, str]]:
    """
    Return a set of node keys (pn_lower, rev_lower) that can be deleted without breaking other assemblies.

    A node is deletable iff *all* of its parents (BOMLink.parent_*) are also deletable.
    The root node is treated as deletable.
    """
    deletable: set[tuple[str, str]] = set(key_to_pair.keys())
    changed = True
    while changed:
        changed = False
        for key in list(deletable):
            if key == root_key:
                continue
            pn, rev = key_to_pair.get(key, ("", ""))
            if not pn:
                deletable.discard(key)
                changed = True
                continue
            q = BOMLink.objects(child_pn__iexact=pn, child_rev__iexact=rev).only("parent_pn", "parent_rev")
            blocked = False
            for link in q:
                parent_pn = (getattr(link, "parent_pn", None) or "").strip()
                parent_rev = clean_rev(getattr(link, "parent_rev", None) or "")
                parent_key = (parent_pn.lower(), parent_rev.lower())
                if parent_key not in deletable:
                    blocked = True
                    break
            if blocked:
                deletable.discard(key)
                changed = True
    return deletable


def delete_part_and_refs_cascade(
    pn: str,
    rev: str | None,
    *,
    delete_children: bool = False,
    delete_files: bool = False,
) -> Dict[str, Any]:
    """
    Delete a part and (optionally) its BOM descendants, but only when descendants are not referenced
    by any other remaining assembly. When delete_files is True, physical files related to each
    deleted (pn, rev) pair are also removed from the server storage.
    """
    pn_clean = (pn or "").strip()
    rev_clean = clean_rev(rev)
    if not pn_clean:
        return {
            "delete_children": bool(delete_children),
            "delete_files": bool(delete_files),
            **delete_part_and_refs(pn, rev, delete_files=delete_files),
        }

    if not delete_children:
        return {
            "delete_children": False,
            "delete_files": bool(delete_files),
            **delete_part_and_refs(pn_clean, rev_clean, delete_files=delete_files),
        }

    root_key, key_to_pair = _collect_bom_descendants(pn_clean, rev_clean)
    deletable_keys = _safe_deletable_subtree(root_key, key_to_pair)
    child_keys = [k for k in deletable_keys if k != root_key]
    skipped_children = max(0, (len(key_to_pair) - 1) - len(child_keys))

    totals = {
        "deleted_parts": 0,
        "deleted_files": 0,
        "deleted_bom_links": 0,
        "deleted_revisions": 0,
        "updated_jobs": 0,
        "updated_orders": 0,
        "deleted_physical_files": 0,
        "deleted_thumb_files": 0,
        "deleted_extra_files": 0,
        "deleted_extra_records": 0,
        "deleted_drawing_markups": 0,
    }

    def _sum_into(res: Dict[str, int]) -> None:
        for k in totals.keys():
            try:
                totals[k] += int(res.get(k) or 0)
            except Exception:
                pass

    # Delete children first, then root.
    for key in sorted(child_keys):
        child_pn, child_rev = key_to_pair.get(key, ("", ""))
        if not child_pn:
            continue
        _sum_into(delete_part_and_refs(child_pn, child_rev, delete_files=delete_files))

    _sum_into(delete_part_and_refs(pn_clean, rev_clean, delete_files=delete_files))

    return {
        "delete_children": True,
        "delete_files": bool(delete_files),
        "children_found": max(0, len(key_to_pair) - 1),
        "children_deleted": int(len(child_keys)),
        "children_skipped": int(skipped_children),
        **totals,
    }
