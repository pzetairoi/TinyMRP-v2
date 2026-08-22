# app/views/part_drawing_markups.py — drawing markup layers + review threads API
from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.models.part import Part
from app.services.authorization import (
    authorise_part_access,
    has_permission,
    require_permission,
    uses_portal_presentation,
)
from app.services.audit import log_action
from app.services.part_drawing_markups import (
    MAX_CANVAS_BYTES,
    MarkupConflictError,
    MarkupTooLargeError,
    MarkupValidationError,
    add_thread_message,
    create_thread,
    delete_thread,
    find_drawing_source,
    find_thread,
    get_markup_layer,
    save_markup_layer,
    serialize_markup,
    set_thread_status,
    source_fingerprint_for,
    update_thread_priority,
    validate_canvas_json,
)
from app.services.part_norm import clean_rev, clean_rev_or_none
from app.services.notifications import notify_part_activity, sync_linked_notification_lifecycle
from app.services.part_review_status import sync_part_review_status

logger = logging.getLogger(__name__)


bp = Blueprint("part_drawing_markups_api", __name__, url_prefix="/api")


def _error(status: int, error: str, message: str = ""):
    return jsonify({"ok": False, "error": error, "message": message or error}), status


def _find_part(pn: str, rev: str | None) -> Part | None:
    pn = (pn or "").strip()
    if not pn:
        return None
    rev_clean = clean_rev_or_none(rev)
    if rev_clean is not None:
        return Part.objects(part_number__iexact=pn, revision__iexact=rev_clean).first()
    return Part.objects(part_number__iexact=pn).order_by("-updated_at").first()


def _part_allowed(part: Part) -> bool:
    return authorise_part_access(
        current_user,
        part.part_number,
        part.revision or "",
    ).allowed


def _can_edit_markups() -> bool:
    return has_permission(current_user, "markups.write")


def _user_email() -> str:
    return str(getattr(current_user, "email", "") or "")


def _thread_participants(thread) -> set[str]:
    participants = {str(getattr(thread, "created_by", "") or "").strip()}
    participants.update(str(getattr(message, "author", "") or "").strip() for message in (thread.messages or []))
    return {email for email in participants if email}


def _page_number(value) -> int:
    try:
        page = int(value)
    except Exception:
        return 1
    return page if page >= 1 else 1


def _resolve_context(pn: str, data: dict):
    """Common part + drawing source resolution. Returns (part, pf, fingerprint,
    page_number, error_response). Errors follow the structured JSON shape."""
    rev = data.get("rev") if "rev" in data else request.args.get("rev")
    part = _find_part(pn, rev)
    if not part:
        return None, None, "", 1, _error(404, "not_found", "part not found")
    if not _part_allowed(part):
        return None, None, "", 1, _error(403, "forbidden", "part access denied")

    source_file_id = str(data.get("source_file_id") or request.args.get("source_file_id") or "").strip()
    if not source_file_id:
        return None, None, "", 1, _error(400, "invalid", "source_file_id is required")
    pf = find_drawing_source(part.part_number, part.revision or "", source_file_id)
    if not pf:
        return None, None, "", 1, _error(404, "source_not_found", "drawing source not found for this part/revision")

    fingerprint = source_fingerprint_for(pf)
    submitted = str(data.get("source_fingerprint") or request.args.get("source_fingerprint") or "").strip()
    if submitted and submitted != fingerprint:
        return None, None, "", 1, _error(
            409,
            "stale_source",
            "the drawing file has changed since this markup layer was loaded",
        )

    page_number = _page_number(data.get("page_number") or request.args.get("page_number") or 1)
    return part, pf, fingerprint, page_number, None


def _audit(action: str, part: Part, meta: dict | None = None) -> None:
    try:
        log_action(
            action,
            resource_type="part",
            resource=f"{part.part_number}:{clean_rev(part.revision or '')}",
            meta=meta or {},
        )
    except Exception:
        logger.exception("audit log failed for markup action %s", action)


def _external_safe_label(value) -> str:
    label = str(value or "").strip()
    return label if label and "@" not in label else "External reviewer"


def _sanitize_external_markup(payload: dict) -> dict:
    """Remove directory identities and storage hints from portal responses."""

    if not uses_portal_presentation(
        current_user,
        "markups.read",
        resource_type="parts",
    ):
        return payload
    source = payload.get("source")
    if isinstance(source, dict):
        source.pop("rel_path", None)
    for thread in payload.get("threads") or []:
        if not isinstance(thread, dict):
            continue
        created_label = _external_safe_label(thread.get("created_by_display"))
        thread["created_by"] = created_label
        thread["created_by_display"] = created_label
        for key in ("updated_by", "resolved_by"):
            if thread.get(key):
                thread[key] = _external_safe_label(thread.get(key))
        for profile_key in ("created_by_profile",):
            profile = thread.get(profile_key)
            if isinstance(profile, dict):
                safe_label = _external_safe_label(
                    profile.get("display_name") or profile.get("label")
                )
                thread[profile_key] = {
                    "display_name": safe_label,
                    "label": safe_label,
                    "initials": profile.get("initials") or "ER",
                    "avatar_color": profile.get("avatar_color") or "#1d4ed8",
                    "avatar_shape": profile.get("avatar_shape") or "circle",
                }
        for message in thread.get("messages") or []:
            if not isinstance(message, dict):
                continue
            label = _external_safe_label(message.get("author_display"))
            message["author"] = label
            message["author_display"] = label
            profile = message.get("author_profile")
            if isinstance(profile, dict):
                message["author_profile"] = {
                    "display_name": label,
                    "label": label,
                    "initials": profile.get("initials") or "ER",
                    "avatar_color": profile.get("avatar_color") or "#1d4ed8",
                    "avatar_shape": profile.get("avatar_shape") or "circle",
                }
    return payload


def _markup_response(doc, *, part: Part, pf, fingerprint: str, page_number: int, status: int = 200):
    payload = serialize_markup(
        doc,
        part_number=part.part_number,
        revision=clean_rev(part.revision or ""),
        source_file=pf,
        fingerprint=fingerprint,
        page_number=page_number,
        can_edit=_can_edit_markups(),
    )
    return jsonify(_sanitize_external_markup(payload)), status


def _conflict_response(exc: MarkupConflictError, *, part: Part, pf, fingerprint: str, page_number: int):
    _audit("part.markup.conflict", part, {"source_file_id": str(pf.id), "page_number": page_number})
    payload = serialize_markup(
        exc.current,
        part_number=part.part_number,
        revision=clean_rev(part.revision or ""),
        source_file=pf,
        fingerprint=fingerprint,
        page_number=page_number,
        can_edit=_can_edit_markups(),
    )
    payload["ok"] = False
    payload["error"] = "conflict"
    payload["message"] = "the markup layer was modified by someone else; reload before saving"
    return jsonify(_sanitize_external_markup(payload)), 409


@bp.get("/parts/<path:pn>/drawing-markups")
@login_required
@require_permission("markups.read")
def drawing_markups_get(pn: str):
    part, pf, fingerprint, page_number, err = _resolve_context(pn, {})
    if err:
        return err
    doc = get_markup_layer(part.part_number, part.revision or "", str(pf.id), fingerprint, page_number)
    _audit(
        "part.markup.view",
        part,
        {"source_file_id": str(pf.id), "page_number": page_number, "version": int(doc.version or 0) if doc else 0},
    )
    return _markup_response(doc, part=part, pf=pf, fingerprint=fingerprint, page_number=page_number)


@bp.put("/parts/<path:pn>/drawing-markups")
@login_required
@require_permission("markups.write")
def drawing_markups_put(pn: str):
    if (request.content_length or 0) > MAX_CANVAS_BYTES:
        return _error(413, "too_large", "markup payload exceeds the 2 MiB limit")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error(400, "invalid", "a JSON body is required")

    part, pf, fingerprint, page_number, err = _resolve_context(pn, data)
    if err:
        return err
    if not _can_edit_markups():
        return _error(403, "forbidden", "markup editing not permitted")

    if "expected_version" not in data:
        return _error(400, "invalid", "expected_version is required")
    try:
        expected_version = int(data.get("expected_version"))
    except Exception:
        return _error(400, "invalid", "expected_version must be an integer")
    if expected_version < 0:
        return _error(400, "invalid", "expected_version must be >= 0")

    try:
        canvas_json = validate_canvas_json(data.get("canvas_json"))
    except MarkupTooLargeError as exc:
        return _error(413, "too_large", str(exc))
    except MarkupValidationError as exc:
        return _error(400, "invalid_canvas", str(exc))

    try:
        doc = save_markup_layer(
            part=part,
            source_file=pf,
            fingerprint=fingerprint,
            page_number=page_number,
            canvas_json=canvas_json,
            expected_version=expected_version,
            user_email=_user_email(),
        )
    except MarkupConflictError as exc:
        return _conflict_response(exc, part=part, pf=pf, fingerprint=fingerprint, page_number=page_number)

    _audit(
        "part.markup.save",
        part,
        {
            "source_file_id": str(pf.id),
            "page_number": page_number,
            "object_count": len(canvas_json.get("objects") or []),
            "version": int(doc.version or 0),
        },
    )
    sync_part_review_status(part)
    return _markup_response(doc, part=part, pf=pf, fingerprint=fingerprint, page_number=page_number)


def _load_layer_or_error(pn: str, data: dict):
    part, pf, fingerprint, page_number, err = _resolve_context(pn, data)
    if err:
        return None, None, None, "", 1, err
    doc = get_markup_layer(part.part_number, part.revision or "", str(pf.id), fingerprint, page_number)
    if not doc:
        return None, None, None, "", 1, _error(404, "not_found", "no markup layer exists for this drawing yet")
    return doc, part, pf, fingerprint, page_number, None


@bp.post("/parts/<path:pn>/drawing-markups/threads")
@login_required
@require_permission("markups.write")
def drawing_markup_thread_create(pn: str):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error(400, "invalid", "a JSON body is required")
    doc, part, pf, fingerprint, page_number, err = _load_layer_or_error(pn, data)
    if err:
        return err
    try:
        thread = create_thread(
            doc,
            object_ids=data.get("object_ids"),
            title=data.get("title"),
            priority=data.get("priority") or "normal",
            message_text=data.get("message"),
            user_email=_user_email(),
        )
    except MarkupTooLargeError as exc:
        return _error(413, "too_large", str(exc))
    except MarkupValidationError as exc:
        return _error(400, "invalid", str(exc))
    _audit(
        "part.markup.thread.create",
        part,
        {
            "source_file_id": str(pf.id),
            "page_number": page_number,
            "thread_id": str(thread.id),
            "priority": str(thread.priority),
            "version": int(doc.version or 0),
        },
    )
    try:
        notify_part_activity(
            part,
            actor_email=_user_email(),
            text=str(data.get("message") or ""),
            title=f"Markup review on {part.part_number}: {thread.title or 'Review'}",
            thread_id=str(thread.id),
        )
    except Exception:
        # Notification failures must not roll back the markup the user just
        # saved, but silently dropping them means nobody learns that review
        # notifications have stopped working.
        logger.warning("markup thread notification failed", exc_info=True)
    sync_part_review_status(part)
    return _markup_response(doc, part=part, pf=pf, fingerprint=fingerprint, page_number=page_number, status=201)


@bp.post("/parts/<path:pn>/drawing-markups/threads/<thread_id>/messages")
@login_required
@require_permission("markups.write")
def drawing_markup_thread_reply(pn: str, thread_id: str):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error(400, "invalid", "a JSON body is required")
    doc, part, pf, fingerprint, page_number, err = _load_layer_or_error(pn, data)
    if err:
        return err
    thread = find_thread(doc, thread_id)
    if not thread:
        return _error(404, "thread_not_found", "review thread not found")
    try:
        message = add_thread_message(doc, thread, text=data.get("text"), user_email=_user_email())
    except MarkupTooLargeError as exc:
        return _error(413, "too_large", str(exc))
    except MarkupValidationError as exc:
        return _error(400, "invalid", str(exc))
    _audit(
        "part.markup.thread.reply",
        part,
        {
            "source_file_id": str(pf.id),
            "page_number": page_number,
            "thread_id": str(thread.id),
            "version": int(doc.version or 0),
        },
    )
    try:
        notify_part_activity(
            part,
            actor_email=_user_email(),
            text=str(message.text or ""),
            title=f"Reply on {part.part_number}: {thread.title or 'Markup review'}",
            participant_emails=_thread_participants(thread),
            thread_id=str(thread.id),
            kind="thread_update",
        )
    except Exception:
        logger.warning("markup reply notification failed", exc_info=True)
    sync_part_review_status(part)
    return _markup_response(doc, part=part, pf=pf, fingerprint=fingerprint, page_number=page_number)


@bp.patch("/parts/<path:pn>/drawing-markups/threads/<thread_id>")
@login_required
@require_permission("markups.moderate")
def drawing_markup_thread_patch(pn: str, thread_id: str):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error(400, "invalid", "a JSON body is required")
    doc, part, pf, fingerprint, page_number, err = _load_layer_or_error(pn, data)
    if err:
        return err
    thread = find_thread(doc, thread_id)
    if not thread:
        return _error(404, "thread_not_found", "review thread not found")

    action = str(data.get("action") or "").strip().lower()
    priority = data.get("priority")
    if not action and priority is None:
        return _error(400, "invalid", "provide an action ('resolve'/'reopen') and/or a priority")
    try:
        if action:
            set_thread_status(doc, thread, action=action, user_email=_user_email())
            _audit(
                f"part.markup.thread.{'resolve' if action == 'resolve' else 'reopen'}",
                part,
                {
                    "source_file_id": str(pf.id),
                    "page_number": page_number,
                    "thread_id": str(thread.id),
                    "version": int(doc.version or 0),
                },
            )
        if priority is not None:
            update_thread_priority(doc, thread, priority=priority, user_email=_user_email())
    except MarkupValidationError as exc:
        return _error(400, "invalid", str(exc))
    try:
        change = action or (f"priority changed to {priority}" if priority is not None else "updated")
        notify_part_activity(
            part,
            actor_email=_user_email(),
            text=f"Markup review {change}.",
            title=f"Review updated on {part.part_number}: {thread.title or 'Markup review'}",
            participant_emails=_thread_participants(thread),
            thread_id=str(thread.id),
            kind="thread_update",
        )
    except Exception:
        logger.warning("markup thread update notification failed", exc_info=True)
    if action:
        try:
            sync_linked_notification_lifecycle(
                part,
                thread_id=str(thread.id),
                current=action == "reopen",
                reason="open" if action == "reopen" else "resolved",
            )
        except Exception:
            logger.warning("markup notification lifecycle sync failed", exc_info=True)
    sync_part_review_status(part)
    return _markup_response(doc, part=part, pf=pf, fingerprint=fingerprint, page_number=page_number)


@bp.delete("/parts/<path:pn>/drawing-markups/threads/<thread_id>")
@login_required
@require_permission("markups.moderate")
def drawing_markup_thread_delete(pn: str, thread_id: str):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    doc, part, pf, fingerprint, page_number, err = _load_layer_or_error(pn, data)
    if err:
        return err
    thread = find_thread(doc, thread_id)
    if not thread:
        return _error(404, "thread_not_found", "review thread not found")
    participants = _thread_participants(thread)
    title = str(thread.title or "Markup review")
    delete_thread(doc, thread, user_email=_user_email())
    _audit(
        "part.markup.thread.delete",
        part,
        {
            "source_file_id": str(pf.id),
            "page_number": page_number,
            "thread_id": str(thread_id),
            "version": int(doc.version or 0),
        },
    )
    try:
        notify_part_activity(
            part,
            actor_email=_user_email(),
            text="The review thread was deleted; the markup objects stay on the drawing.",
            title=f"Review deleted on {part.part_number}: {title}",
            participant_emails=participants,
            thread_id=str(thread_id),
            kind="thread_update",
        )
    except Exception:
        logger.warning("markup thread delete notification failed", exc_info=True)
    try:
        sync_linked_notification_lifecycle(
            part,
            thread_id=str(thread_id),
            current=False,
            reason="deleted",
        )
    except Exception:
        logger.warning("markup notification lifecycle sync failed", exc_info=True)
    sync_part_review_status(part)
    return _markup_response(doc, part=part, pf=pf, fingerprint=fingerprint, page_number=page_number)
