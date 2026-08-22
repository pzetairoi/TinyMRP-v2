from __future__ import annotations

import re
from typing import Iterable, Sequence
from urllib.parse import quote

from app.models.auth import User
from app.models.notification import UserNotification
from app.models.part_annotation import PartAnnotation
from app.models.part_drawing_markup import PartDrawingMarkup
from app.services.acl import allowed_parts_for, part_is_allowed
from app.services.part_norm import clean_rev
from app.services.timezone_utils import utc_now


MENTION_RE = re.compile(r"(?<![\w@])@([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", re.IGNORECASE)


def _part_key(part_number: object, revision: object) -> tuple[str, str]:
    return (
        str(part_number or "").strip().casefold(),
        clean_rev(revision).casefold(),
    )


def notification_lifecycle(
    rows: Sequence[UserNotification],
    user: User,
) -> tuple[list[tuple[UserNotification, str]], list[tuple[UserNotification, str]]]:
    """Split notification events into current work and history.

    Notification documents are an event history, while the home page is a work
    queue.  Resolve the linked comment/review against its live state so deleted
    and resolved work cannot remain in the queue.  Older events for the same
    still-open conversation are retained as history, leaving one clear current
    item per conversation.
    """
    from app.models.part import Part
    from app.services.authorization import has_permission, scope_queryset

    ordered = list(rows)
    part_numbers = {
        str(row.part_number or "").strip()
        for row in ordered
        if str(row.part_number or "").strip()
    }
    allowed_parts: set[tuple[str, str]] = set()
    if part_numbers:
        scoped_parts = scope_queryset(
            Part.objects(part_number__in=tuple(part_numbers)),
            user,
            "parts",
        ).only("part_number", "revision")
        allowed_parts = {
            _part_key(part.part_number, part.revision)
            for part in scoped_parts
        }

    comment_states: dict[tuple[str, str, str], str] = {}
    thread_states: dict[tuple[str, str, str], str] = {}
    if allowed_parts and has_permission(user, "comments.read"):
        for annotation in PartAnnotation.objects(
            part_number__in=tuple(part_numbers)
        ).only("part_number", "revision", "comments"):
            key = _part_key(annotation.part_number, annotation.revision)
            if key not in allowed_parts:
                continue
            for comment in annotation.comments or ():
                comment_id = str((comment or {}).get("id") or "").strip()
                if not comment_id:
                    continue
                status = str((comment or {}).get("status") or "open").strip().lower()
                comment_states[(*key, comment_id)] = "resolved" if status == "resolved" else "open"

    if allowed_parts and has_permission(user, "markups.read"):
        for layer in PartDrawingMarkup.objects(
            part_number__in=tuple(part_numbers)
        ).only("part_number", "revision", "threads"):
            key = _part_key(layer.part_number, layer.revision)
            if key not in allowed_parts:
                continue
            for thread in layer.threads or ():
                thread_id = str(getattr(thread, "id", "") or "").strip()
                if not thread_id:
                    continue
                status = str(getattr(thread, "status", "open") or "open").strip().lower()
                thread_states[(*key, thread_id)] = "resolved" if status == "resolved" else "open"

    current: list[tuple[UserNotification, str]] = []
    history: list[tuple[UserNotification, str]] = []
    seen_open_conversations: set[tuple[str, str, str, str]] = set()
    can_read_comments = has_permission(user, "comments.read")
    can_read_markups = has_permission(user, "markups.read")

    for row in ordered:
        part_key = _part_key(row.part_number, row.revision)
        has_part_link = bool(part_key[0])
        if has_part_link and part_key not in allowed_parts:
            # Access may have been revoked since the event was created.  Do not
            # disclose stale part content through notification history.
            history.append((row, "inaccessible"))
            continue

        comment_id = str(row.comment_id or "").strip()
        thread_id = str(row.thread_id or "").strip()
        if comment_id:
            if not can_read_comments:
                history.append((row, "inaccessible"))
                continue
            conversation = ("comment", *part_key, comment_id)
            status = comment_states.get((*part_key, comment_id))
        elif thread_id:
            if not can_read_markups:
                history.append((row, "inaccessible"))
                continue
            conversation = ("thread", *part_key, thread_id)
            status = thread_states.get((*part_key, thread_id))
        else:
            # Legacy or account-level events have no live conversation to
            # inspect.  Unread means current; read means retained history.
            if row.read_at is None:
                current.append((row, "unread"))
            else:
                history.append((row, "read"))
            continue

        if status == "open" and conversation not in seen_open_conversations:
            seen_open_conversations.add(conversation)
            current.append((row, "open"))
        elif status == "open":
            history.append((row, "previous_activity"))
        elif status == "resolved":
            history.append((row, "resolved"))
        else:
            history.append((row, "deleted"))

    return current, history


def persist_notification_lifecycle(
    rows: Iterable[tuple[UserNotification, str]],
    lifecycle: str,
) -> None:
    """Persist lifecycle classifications without rewriting event content."""
    for row, reason in rows:
        if row.lifecycle == lifecycle and row.lifecycle_reason == reason:
            continue
        row.update(set__lifecycle=lifecycle, set__lifecycle_reason=reason)
        row.lifecycle = lifecycle
        row.lifecycle_reason = reason


def sync_linked_notification_lifecycle(
    part,
    *,
    comment_id: str = "",
    thread_id: str = "",
    current: bool,
    reason: str,
) -> None:
    """Keep every recipient's latest event aligned with a conversation state."""
    comment_id = str(comment_id or "").strip()
    thread_id = str(thread_id or "").strip()
    if not comment_id and not thread_id:
        return
    filters = {
        "part_number": str(getattr(part, "part_number", "") or "").strip(),
        "revision": clean_rev(getattr(part, "revision", "") or ""),
    }
    filters["comment_id" if comment_id else "thread_id"] = comment_id or thread_id
    rows = list(UserNotification.objects(**filters).order_by("recipient", "-created_at"))
    seen_recipients: set[str] = set()
    for row in rows:
        recipient_id = str(getattr(row.recipient, "id", "") or "")
        is_latest = recipient_id not in seen_recipients
        seen_recipients.add(recipient_id)
        lifecycle = "current" if current and is_latest else "history"
        lifecycle_reason = reason if lifecycle == "current" or not current else "previous_activity"
        row.update(
            set__lifecycle=lifecycle,
            set__lifecycle_reason=lifecycle_reason,
        )


def normalize_email(value: object) -> str:
    return str(value or "").strip().lower()


def extract_mention_emails(*texts: object) -> set[str]:
    found: set[str] = set()
    for value in texts:
        for match in MENTION_RE.finditer(str(value or "")):
            found.add(normalize_email(match.group(1)))
    return found


def part_url(part_number: str, revision: str = "") -> str:
    base = f"/ui/part/{quote(str(part_number or '').strip(), safe='')}"
    rev = str(revision or "").strip()
    return f"{base}?rev={quote(rev, safe='')}&tab=reviews" if rev else f"{base}?tab=reviews"


def part_uploader_email(part) -> str:
    attrs = dict(getattr(part, "attrs", {}) or {})
    for key in ("uploader", "uploaded_by", "uploadedby", "author", "drawnby"):
        email = normalize_email(attrs.get(key))
        if email:
            return email
    return ""


def active_users_by_email(emails: Iterable[str]) -> dict[str, User]:
    wanted = {normalize_email(email) for email in emails if normalize_email(email)}
    if not wanted:
        return {}
    return {
        normalize_email(user.email): user
        for user in User.objects(email__in=sorted(wanted), active=True)
    }


def recipients_with_part_access(part, emails: Iterable[str]) -> set[str]:
    users = active_users_by_email(emails)
    allowed: set[str] = set()
    for email, user in users.items():
        try:
            scoped = allowed_parts_for(user)
            if isinstance(scoped, set) and not part_is_allowed(scoped, part.part_number, part.revision or ""):
                continue
        except Exception:
            continue
        allowed.add(email)
    return allowed


def create_notifications(
    *,
    recipient_emails: Iterable[str],
    actor_email: str,
    kind: str,
    title: str,
    body: str,
    url: str,
    part_number: str = "",
    revision: str = "",
    thread_id: str = "",
    comment_id: str = "",
    lifecycle: str = "current",
    lifecycle_reason: str = "open",
) -> list[UserNotification]:
    actor = normalize_email(actor_email)
    recipients = {normalize_email(email) for email in recipient_emails if normalize_email(email)}
    recipients.discard(actor)
    users = active_users_by_email(recipients)
    lifecycle = "history" if lifecycle == "history" else "current"
    created: list[UserNotification] = []
    for email in sorted(users):
        if lifecycle == "current" and (thread_id or comment_id):
            previous = UserNotification.objects(
                recipient=users[email],
                part_number=str(part_number or "").strip(),
                revision=clean_rev(revision),
            )
            previous = (
                previous.filter(thread_id=str(thread_id).strip())
                if thread_id
                else previous.filter(comment_id=str(comment_id).strip())
            )
            previous.update(
                set__lifecycle="history",
                set__lifecycle_reason="previous_activity",
            )
        doc = UserNotification(
            recipient=users[email],
            actor_email=actor,
            kind=kind,
            title=str(title or "Notification").strip()[:180],
            body=str(body or "").strip()[:500],
            url=str(url or "/app").strip()[:500],
            part_number=str(part_number or "").strip(),
            revision=clean_rev(revision),
            thread_id=str(thread_id or "").strip(),
            comment_id=str(comment_id or "").strip(),
            lifecycle=lifecycle,
            lifecycle_reason=str(lifecycle_reason or "").strip(),
            created_at=utc_now(),
        ).save()
        created.append(doc)
    return created


def notify_part_activity(
    part,
    *,
    actor_email: str,
    text: str,
    title: str,
    participant_emails: Iterable[str] = (),
    thread_id: str = "",
    comment_id: str = "",
    kind: str = "part_review",
) -> list[UserNotification]:
    mentions = extract_mention_emails(text, title)
    general = {part_uploader_email(part), *participant_emails} - mentions
    mentions = recipients_with_part_access(part, mentions)
    general = recipients_with_part_access(part, general)
    common = {
        "actor_email": actor_email,
        "body": text,
        "url": part_url(part.part_number, part.revision or ""),
        "part_number": part.part_number,
        "revision": part.revision or "",
        "thread_id": thread_id,
        "comment_id": comment_id,
    }
    created = create_notifications(recipient_emails=mentions, kind="mention", title=f"You were mentioned: {title}", **common)
    created.extend(create_notifications(recipient_emails=general, kind=kind, title=title, **common))
    return created
