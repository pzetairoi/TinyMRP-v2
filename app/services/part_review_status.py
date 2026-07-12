from __future__ import annotations

from app.models.part import Part
from app.models.part_annotation import PartAnnotation
from app.models.part_drawing_markup import PartDrawingMarkup
from app.services.part_norm import clean_rev


SEVERITY_RANK = {"": 0, "low": 1, "normal": 2, "high": 3}


def compute_part_review_status(part: Part) -> dict[str, object]:
    pn = str(part.part_number or "").strip()
    rev = clean_rev(part.revision or "")
    count = 0
    severity = ""

    annotation = PartAnnotation.objects(part_number=pn, revision=rev).first()
    for comment in list(getattr(annotation, "comments", []) or []):
        if not isinstance(comment, dict) or not str(comment.get("text") or "").strip():
            continue
        if str(comment.get("status") or "open").strip().lower() == "resolved":
            continue
        count += 1
        priority = str(comment.get("priority") or "low").strip().lower()
        if priority not in SEVERITY_RANK:
            priority = "low"
        if SEVERITY_RANK[priority] > SEVERITY_RANK[severity]:
            severity = priority

    for layer in PartDrawingMarkup.objects(part_number__iexact=pn, revision__iexact=rev):
        for thread in layer.threads or []:
            if str(thread.status or "") != "open":
                continue
            count += 1
            priority = str(thread.priority or "normal").strip().lower()
            if priority not in SEVERITY_RANK:
                priority = "normal"
            if SEVERITY_RANK[priority] > SEVERITY_RANK[severity]:
                severity = priority

    return {"count": count, "severity": severity if count else "", "pending": count > 0}


def sync_part_review_status(part: Part) -> dict[str, object]:
    status = compute_part_review_status(part)
    Part.objects(id=part.id).update_one(
        set__pending_review_count=int(status["count"]),
        set__pending_review_severity=str(status["severity"]),
    )
    part.pending_review_count = int(status["count"])
    part.pending_review_severity = str(status["severity"])
    return status


def part_review_status_map() -> dict[tuple[str, str], dict[str, object]]:
    statuses: dict[tuple[str, str], dict[str, object]] = {}

    def ensure(key: tuple[str, str]) -> dict[str, object]:
        return statuses.setdefault(key, {"count": 0, "severity": "", "pending": False})

    for annotation in PartAnnotation.objects.only("part_number", "revision", "comments"):
        key = (str(annotation.part_number or "").strip(), clean_rev(annotation.revision or ""))
        row = ensure(key)
        for comment in list(annotation.comments or []):
            if not isinstance(comment, dict) or not str(comment.get("text") or "").strip():
                continue
            if str(comment.get("status") or "open").strip().lower() == "resolved":
                continue
            row["count"] = int(row["count"]) + 1
            priority = str(comment.get("priority") or "low").strip().lower()
            if priority not in SEVERITY_RANK:
                priority = "low"
            if SEVERITY_RANK[priority] > SEVERITY_RANK[str(row["severity"])]:
                row["severity"] = priority

    for layer in PartDrawingMarkup.objects.only("part_number", "revision", "threads"):
        key = (str(layer.part_number or "").strip(), clean_rev(layer.revision or ""))
        row = ensure(key)
        for thread in layer.threads or []:
            if str(thread.status or "") != "open":
                continue
            row["count"] = int(row["count"]) + 1
            priority = str(thread.priority or "normal").strip().lower()
            if priority not in SEVERITY_RANK:
                priority = "normal"
            if SEVERITY_RANK[priority] > SEVERITY_RANK[str(row["severity"])]:
                row["severity"] = priority

    for row in statuses.values():
        row["pending"] = int(row["count"]) > 0
        if not row["pending"]:
            row["severity"] = ""
    return statuses
