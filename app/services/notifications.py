from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import quote

from app.models.auth import User
from app.models.notification import UserNotification
from app.services.acl import allowed_parts_for, part_is_allowed
from app.services.timezone_utils import utc_now


MENTION_RE = re.compile(r"(?<![\w@])@([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", re.IGNORECASE)


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
) -> list[UserNotification]:
    actor = normalize_email(actor_email)
    recipients = {normalize_email(email) for email in recipient_emails if normalize_email(email)}
    recipients.discard(actor)
    users = active_users_by_email(recipients)
    created: list[UserNotification] = []
    for email in sorted(users):
        doc = UserNotification(
            recipient=users[email],
            actor_email=actor,
            kind=kind,
            title=str(title or "Notification").strip()[:180],
            body=str(body or "").strip()[:500],
            url=str(url or "/app").strip()[:500],
            part_number=str(part_number or "").strip(),
            revision=str(revision or "").strip(),
            thread_id=str(thread_id or "").strip(),
            comment_id=str(comment_id or "").strip(),
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
