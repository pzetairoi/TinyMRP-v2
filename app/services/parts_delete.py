from __future__ import annotations

from datetime import datetime
from typing import Dict, Tuple

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
