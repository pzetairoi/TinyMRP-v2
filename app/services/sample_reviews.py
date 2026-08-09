"""Deterministic, idempotent review history for the CV03 demo dataset."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.models.artifact import PartFile
from app.models.part import Part
from app.models.part_annotation import PartAnnotation
from app.models.part_drawing_markup import (
    PartDrawingMarkup,
    PartDrawingMarkupMessage,
    PartDrawingMarkupThread,
)
from app.services.part_annotations import sync_annotation_search_fields
from app.services.part_drawing_markups import source_fingerprint_for
from app.services.part_review_status import sync_part_review_status
from app.services.sample_dataset import MANAGED_ROOT, PART_NUMBER, REVISION, load_sample_manifest


DEMO_PREFIX = "demo-cv03-"


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _email(users: dict[str, object], scenario: str) -> str:
    return str(getattr(users[scenario], "email", "") or "")


def _reply(reply_id: str, ts: str, author: str, text: str) -> dict:
    return {"id": reply_id, "ts": ts, "author": author, "text": text}


def _comment(
    comment_id: str,
    ts: str,
    author: str,
    text: str,
    *,
    priority: str = "normal",
    status: str = "open",
    replies: list[dict] | None = None,
) -> dict:
    return {
        "id": comment_id,
        "ts": ts,
        "author": author,
        "text": text,
        "priority": priority,
        "status": status,
        "replies": list(replies or []),
    }


def _review_comments(users: dict[str, object]) -> dict[tuple[str, str], list[dict]]:
    customer = _email(users, "customer")
    spares = _email(users, "customer_spares")
    engineer = _email(users, "engineering")
    manager = _email(users, "engineering_manager")
    workshop = _email(users, "workshop")
    commercial = _email(users, "commercial")
    fabrication_release = _email(users, "supplier_unreleased")
    running = _email(users, "supplier_running_gear")
    electrical = _email(users, "supplier_electrical")
    return {
        (PART_NUMBER, REVISION): [
            _comment(
                "demo-cv03-root-clearance",
                "2026-07-13T09:10:00",
                customer,
                "Please confirm drawbar clearance at full lock before the fleet release.",
                priority="high",
                replies=[
                    _reply("demo-cv03-root-clearance-r1", "2026-07-13T10:02:00", engineer, "Checked against the A-revision envelope; markup added around the hitch zone."),
                    _reply("demo-cv03-root-clearance-r2", "2026-07-13T13:45:00", manager, "Frame jig and hitch plate evidence matches the released drawing dimensions."),
                    _reply("demo-cv03-root-clearance-r3", "2026-07-15T08:30:00", workshop, "Physical sweep test passed on the first build."),
                ],
            ),
            _comment(
                "demo-cv03-root-adr",
                "2026-07-17T11:20:00",
                engineer,
                "ADR lamp, reflector and registration-light positions checked against the drawing.",
                priority="high",
                status="resolved",
                replies=[
                    _reply("demo-cv03-root-adr-r1", "2026-07-17T14:10:00", manager, "Compliance layout accepted; keep the loom clear of the spring travel."),
                    _reply("demo-cv03-root-adr-r2", "2026-07-18T09:05:00", customer, "Accepted for the fleet units."),
                ],
            ),
            _comment(
                "demo-cv03-root-finish",
                "2026-07-22T07:55:00",
                workshop,
                "Mask VIN plate lands, earth points and hitch interface before powder coating.",
                priority="normal",
                status="resolved",
                replies=[
                    _reply("demo-cv03-root-finish-r1", "2026-07-22T09:30:00", workshop, "Masking checklist added to the traveller."),
                    _reply("demo-cv03-root-finish-r2", "2026-07-24T15:15:00", engineer, "First-off finish inspection passed."),
                ],
            ),
            _comment(
                "demo-cv03-root-release-request",
                "2026-07-25T09:20:00",
                customer,
                "Please approve CV03-F02 REV B. The parent drawing references it, but our restricted portal correctly prevents us from opening the unreleased frame assembly.",
                priority="high",
                replies=[
                    _reply("demo-cv03-root-release-request-r1", "2026-07-25T10:05:00", engineer, "Approval remains on hold pending the weld-distortion review; the released parent can still be reviewed here."),
                    _reply("demo-cv03-root-release-request-r2", "2026-07-25T11:40:00", manager, "A specifically authorised portal reviewer will validate the held subtree before release."),
                ],
            ),
        ],
        ("CV03-F02", "B"): [
            _comment(
                "demo-cv03-frame-dfm",
                "2026-07-10T08:40:00",
                fabrication_release,
                "Request weld sequence confirmation to control drawbar distortion.",
                priority="high",
                status="resolved",
                replies=[
                    _reply("demo-cv03-frame-dfm-r1", "2026-07-10T10:15:00", engineer, "Use alternating 150 mm runs from the centre outward."),
                    _reply("demo-cv03-frame-dfm-r2", "2026-07-12T16:05:00", fabrication_release, "Trial frame measured within tolerance; sequence accepted."),
                ],
            )
        ],
        ("ADR-HITCH", "A"): [
            _comment(
                "demo-cv03-hitch-spares",
                "2026-07-28T12:25:00",
                spares,
                "Can the replacement hitch ship with fasteners and torque guidance?",
                replies=[
                    _reply("demo-cv03-hitch-spares-r1", "2026-07-28T13:10:00", running, "Yes, the service kit includes the mounting set."),
                    _reply("demo-cv03-hitch-spares-r2", "2026-07-28T15:00:00", commercial, "Kit and freight are included on DEMO-SO-B1."),
                ],
            )
        ],
        ("ADR-LED-IND", ""): [
            _comment(
                "demo-cv03-lamp-connector",
                "2026-07-29T09:05:00",
                spares,
                "Please verify the spare lamp connector matches the installed fleet loom.",
                priority="high",
                status="resolved",
                replies=[
                    _reply("demo-cv03-lamp-connector-r1", "2026-07-29T10:40:00", electrical, "Connector and pin-out verified against the supplied unit."),
                    _reply("demo-cv03-lamp-connector-r2", "2026-07-30T08:15:00", workshop, "Bench connection and function test passed."),
                ],
            )
        ],
    }


def _drawing_source() -> PartFile:
    source = PartFile.objects(
        part_number=PART_NUMBER,
        revision=REVISION,
        ext_group="png",
        is_dwg=True,
    ).first()
    if source:
        return source
    path = MANAGED_ROOT / "png" / "CV03-TR-A01_REV_A_DWG.png"
    entry = next(
        row
        for row in load_sample_manifest()["managed_files"]
        if row["path"] == "png/CV03-TR-A01_REV_A_DWG.png"
    )
    return PartFile(
        part_number=PART_NUMBER,
        revision=REVISION,
        ext_group="png",
        ext="png",
        is_dwg=True,
        rel_path="png/CV03-TR-A01_REV_A_DWG.png",
        path=str(path),
        size=float(entry["bytes"]),
        sha256=entry["sha256"],
        source="sample-fixture",
    ).save()


def _markup_objects() -> list[dict]:
    return [
        {"type": "Rect", "tmObjectId": "demo-cv03-hitch-box", "left": 560, "top": 650, "width": 310, "height": 185, "fill": "rgba(220,38,38,0.08)", "stroke": "#dc2626", "strokeWidth": 6},
        {"type": "Ellipse", "tmObjectId": "demo-cv03-lamp-ring", "left": 210, "top": 805, "rx": 150, "ry": 95, "fill": "rgba(245,158,11,0.08)", "stroke": "#f59e0b", "strokeWidth": 6},
        {"type": "Rect", "tmObjectId": "demo-cv03-vin-mask", "left": 1210, "top": 875, "width": 235, "height": 85, "fill": "rgba(37,99,235,0.08)", "stroke": "#2563eb", "strokeWidth": 5},
        {"type": "Textbox", "tmObjectId": "demo-cv03-loom-note", "left": 920, "top": 405, "width": 360, "text": "Confirm ADR loom route", "fontSize": 36, "fill": "#dc2626", "strokeWidth": 1},
        {"type": "Textbox", "tmObjectId": "demo-cv03-release-note", "left": 900, "top": 1040, "width": 520, "text": "CV03-F02 REV B approval requested", "fontSize": 32, "fill": "#7c3aed", "strokeWidth": 1},
    ]


def _message(message_id: str, author: str, ts: str, text: str) -> PartDrawingMarkupMessage:
    return PartDrawingMarkupMessage(id=message_id, author=author, ts=_ts(ts), text=text)


def _markup_threads(users: dict[str, object]) -> list[PartDrawingMarkupThread]:
    customer = _email(users, "customer")
    engineer = _email(users, "engineering")
    workshop = _email(users, "workshop")
    manager = _email(users, "engineering_manager")
    return [
        PartDrawingMarkupThread(
            id="demo-cv03-thread-hitch", object_ids=["demo-cv03-hitch-box"], title="Hitch clearance review", priority="high", status="open",
            created_by=customer, created_at=_ts("2026-07-13T09:12:00"), updated_by=workshop, updated_at=_ts("2026-07-15T08:31:00"),
            messages=[
                _message("demo-cv03-thread-hitch-m1", customer, "2026-07-13T09:12:00", "Please confirm clearance at full lock."),
                _message("demo-cv03-thread-hitch-m2", engineer, "2026-07-13T10:04:00", "Envelope checked; highlighted zone is the controlling interface."),
                _message("demo-cv03-thread-hitch-m3", manager, "2026-07-13T13:48:00", "Jig measurement agrees with the drawing."),
                _message("demo-cv03-thread-hitch-m4", workshop, "2026-07-15T08:31:00", "Physical sweep passed; leaving open until fleet sign-off."),
            ],
        ),
        PartDrawingMarkupThread(
            id="demo-cv03-thread-lamps", object_ids=["demo-cv03-lamp-ring", "demo-cv03-loom-note"], title="ADR lamp and loom placement", priority="high", status="resolved",
            created_by=engineer, created_at=_ts("2026-07-17T11:22:00"), updated_by=engineer, updated_at=_ts("2026-07-18T09:10:00"), resolved_by=engineer, resolved_at=_ts("2026-07-18T09:10:00"),
            messages=[
                _message("demo-cv03-thread-lamps-m1", engineer, "2026-07-17T11:22:00", "Confirm lamp position and keep the loom above spring travel."),
                _message("demo-cv03-thread-lamps-m2", engineer, "2026-07-17T14:12:00", "Route accepted with the added P-clip location."),
                _message("demo-cv03-thread-lamps-m3", workshop, "2026-07-18T08:50:00", "Installed and function-tested on the first unit."),
            ],
        ),
        PartDrawingMarkupThread(
            id="demo-cv03-thread-vin", object_ids=["demo-cv03-vin-mask"], title="VIN plate masking", priority="normal", status="resolved",
            created_by=workshop, created_at=_ts("2026-07-22T07:57:00"), updated_by=workshop, updated_at=_ts("2026-07-24T15:16:00"), resolved_by=workshop, resolved_at=_ts("2026-07-24T15:16:00"),
            messages=[
                _message("demo-cv03-thread-vin-m1", workshop, "2026-07-22T07:57:00", "Mask this land before powder coat."),
                _message("demo-cv03-thread-vin-m2", workshop, "2026-07-24T15:16:00", "Mask removed and earth continuity verified."),
            ],
        ),
        PartDrawingMarkupThread(
            id="demo-cv03-thread-release", object_ids=["demo-cv03-release-note"], title="Unreleased child approval request", priority="high", status="open",
            created_by=customer, created_at=_ts("2026-07-25T09:22:00"), updated_by=engineer, updated_at=_ts("2026-07-25T10:06:00"),
            messages=[
                _message("demo-cv03-thread-release-m1", customer, "2026-07-25T09:22:00", "We can review this parent drawing but cannot open CV03-F02 REV B. Please approve it when the engineering hold is cleared."),
                _message("demo-cv03-thread-release-m2", engineer, "2026-07-25T10:06:00", "That restriction is intentional. Weld review is still open; an authorised external reviewer can inspect the held subtree."),
            ],
        ),
    ]


def seed_sample_review_history(users: dict[str, object]) -> dict[str, int]:
    comments_total = 0
    annotated_parts = 0
    for pair, demo_comments in _review_comments(users).items():
        part = Part.objects(part_number=pair[0], revision=pair[1]).first()
        if not part:
            continue
        doc = PartAnnotation.objects(part_number=pair[0], revision=pair[1]).first()
        if not doc:
            doc = PartAnnotation(part_number=pair[0], revision=pair[1])
        preserved = [row for row in list(doc.comments or []) if not str(row.get("id") or "").startswith(DEMO_PREFIX)]
        doc.comments = preserved + demo_comments
        if not doc.notes:
            doc.notes = "Owner-approved CV03 demo review dossier."
        doc.updated_at = _ts("2026-08-01T12:00:00")
        doc.save()
        sync_annotation_search_fields(part)
        sync_part_review_status(part)
        comments_total += len(demo_comments)
        annotated_parts += 1

    source = _drawing_source()
    fingerprint = source_fingerprint_for(source)
    markup = PartDrawingMarkup.objects(
        part_number=PART_NUMBER,
        revision=REVISION,
        source_file_id=str(source.id),
        source_fingerprint=fingerprint,
        page_number=1,
    ).first()
    if not markup:
        markup = PartDrawingMarkup(
            part_number=PART_NUMBER,
            revision=REVISION,
            source_file_id=str(source.id),
            source_rel_path=source.rel_path,
            source_fingerprint=fingerprint,
            page_number=1,
            created_by=_email(users, "engineering"),
            created_at=_ts("2026-07-13T09:00:00"),
        )
    canvas = dict(markup.canvas_json or {})
    preserved_objects = [obj for obj in list(canvas.get("objects") or []) if not str(obj.get("tmObjectId") or "").startswith(DEMO_PREFIX)]
    canvas.update({"version": "7.4.0", "objects": preserved_objects + _markup_objects()})
    markup.canvas_json = canvas
    markup.threads = [thread for thread in list(markup.threads or []) if not str(thread.id or "").startswith(DEMO_PREFIX)] + _markup_threads(users)
    markup.canvas_schema_version = 1
    markup.version = max(int(markup.version or 0), 1) + 1
    markup.updated_by = _email(users, "engineering_manager")
    markup.updated_at = _ts("2026-07-24T15:16:00")
    markup.save()
    sync_part_review_status(Part.objects(part_number=PART_NUMBER, revision=REVISION).get())
    return {
        "annotated_parts": annotated_parts,
        "comments": comments_total,
        "markup_threads": len(_markup_threads(users)),
    }


def remove_sample_review_history() -> dict[str, int]:
    removed_comments = 0
    for doc in PartAnnotation.objects:
        original = list(doc.comments or [])
        kept = [row for row in original if not str(row.get("id") or "").startswith(DEMO_PREFIX)]
        removed_comments += len(original) - len(kept)
        if kept or (doc.notes and doc.notes != "Owner-approved CV03 demo review dossier."):
            doc.comments = kept
            if doc.notes == "Owner-approved CV03 demo review dossier.":
                doc.notes = ""
            doc.save()
        else:
            doc.delete()
        part = Part.objects(part_number=doc.part_number, revision=doc.revision).first()
        if part:
            sync_annotation_search_fields(part)
            sync_part_review_status(part)

    removed_threads = 0
    for markup in PartDrawingMarkup.objects(part_number=PART_NUMBER, revision=REVISION):
        objects = list((markup.canvas_json or {}).get("objects") or [])
        kept_objects = [obj for obj in objects if not str(obj.get("tmObjectId") or "").startswith(DEMO_PREFIX)]
        threads = list(markup.threads or [])
        kept_threads = [thread for thread in threads if not str(thread.id or "").startswith(DEMO_PREFIX)]
        removed_threads += len(threads) - len(kept_threads)
        if kept_objects or kept_threads:
            canvas = dict(markup.canvas_json or {})
            canvas["objects"] = kept_objects
            markup.canvas_json = canvas
            markup.threads = kept_threads
            markup.save()
        else:
            markup.delete()
    return {"comments": removed_comments, "markup_threads": removed_threads}
