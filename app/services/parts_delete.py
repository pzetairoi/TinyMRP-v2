from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any, Dict, Tuple

from app.models.part import Part
from app.models.artifact import PartFile
from app.models.bom import BOMLink
from app.models.job import Job
from app.models.order import Order
from app.models.part_revision import PartRevisionHistory
from app.services.biz_utils import calculate_order_totals
from app.services.part_norm import clean_rev


def _match_pn_rev(pn: str, rev: str, target_pn: str, target_rev: str) -> bool:
    return (pn or "").strip().lower() == target_pn and clean_rev(rev).lower() == target_rev


def delete_part_and_refs(pn: str, rev: str | None) -> Dict[str, int]:
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
        }

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
            job.updated_at = datetime.utcnow()
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
            order.updated_at = datetime.utcnow()
            order.save()
            updated_orders += 1

    return {
        "deleted_parts": int(deleted_parts or 0),
        "deleted_files": int(deleted_files or 0),
        "deleted_bom_links": int(deleted_bom_links or 0),
        "deleted_revisions": int(deleted_revisions or 0),
        "updated_jobs": int(updated_jobs or 0),
        "updated_orders": int(updated_orders or 0),
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


def delete_part_and_refs_cascade(pn: str, rev: str | None, *, delete_children: bool = False) -> Dict[str, Any]:
    """
    Delete a part and (optionally) its BOM descendants, but only when descendants are not referenced
    by any other remaining assembly.
    """
    pn_clean = (pn or "").strip()
    rev_clean = clean_rev(rev)
    if not pn_clean:
        return {"delete_children": bool(delete_children), **delete_part_and_refs(pn, rev)}

    if not delete_children:
        return {"delete_children": False, **delete_part_and_refs(pn_clean, rev_clean)}

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
        _sum_into(delete_part_and_refs(child_pn, child_rev))

    _sum_into(delete_part_and_refs(pn_clean, rev_clean))

    return {
        "delete_children": True,
        "children_found": max(0, len(key_to_pair) - 1),
        "children_deleted": int(len(child_keys)),
        "children_skipped": int(skipped_children),
        **totals,
    }
