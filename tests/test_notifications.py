from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.models.auth import Role, User
from app.models.artifact import PartFile
from app.models.notification import UserNotification
from app.models.part import Part
from app.models.part_annotation import PartAnnotation
from app.services.notifications import extract_mention_emails


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _user(email: str, role=None):
    user = User(email=email, password="test", active=True, fs_uniquifier=f"notify-{email}")
    if role is not None:
        user.roles = [role]
    return user.save()


def test_extract_mentions_uses_complete_email_tokens():
    assert extract_mention_emails("Hi @USER@example.com and @other.user@example.org 👍") == {
        "user@example.com",
        "other.user@example.org",
    }
    assert extract_mention_emails("plain@email.example is not an explicit mention") == set()


def test_part_comment_notifies_mention_and_part_uploader(client):
    viewer = Role(
        name="notification_viewer",
        permissions=[
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "parts.read_unreleased",
            "comments.write",
        ],
    ).save()
    actor = _user("actor@example.com", viewer)
    mentioned = _user("mentioned@example.com", viewer)
    uploader = _user("uploader@example.com", viewer)
    Part(
        part_number="NOTIFY-100",
        revision="A",
        description="Notification part",
        attrs={"uploaded_by": uploader.email},
    ).save()
    _login(client, actor)

    response = client.post(
        "/api/parts/NOTIFY-100/comments",
        json={"rev": "A", "text": "Please check this @mentioned@example.com 👍", "priority": "high"},
    )
    assert response.status_code == 200

    mention_row = UserNotification.objects(recipient=mentioned).first()
    upload_row = UserNotification.objects(recipient=uploader).first()
    assert mention_row is not None
    assert mention_row.kind == "mention"
    assert mention_row.url == "/ui/part/NOTIFY-100?rev=A&tab=reviews"
    assert upload_row is not None
    assert upload_row.kind == "part_review"
    assert UserNotification.objects(recipient=actor).count() == 0


def test_notification_api_read_state_and_mentionable_users(client):
    viewer = Role(
        name="notification_api_viewer",
        permissions=[
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "comments.write",
        ],
    ).save()
    user = _user("inbox@example.com", viewer)
    colleague = _user("colleague@example.com", viewer)
    row = UserNotification(
        recipient=user,
        actor_email=colleague.email,
        kind="mention",
        title="You were mentioned",
        body="Please review",
        url="/ui/part/PN-1",
    ).save()
    Part(
        part_number="MENTION-1",
        revision="",
        description="Mention scope",
        attrs={"approved": "yes"},
    ).save()
    _login(client, user)

    listing = client.get("/api/notifications")
    assert listing.status_code == 200
    payload = listing.get_json()
    assert payload["unread_count"] == 1
    assert payload["notifications"][0]["id"] == str(row.id)
    assert payload["notifications"][0]["unread"] is True

    suggestions = client.get("/api/users/mentionable?q=colleague&pn=MENTION-1&rev=")
    assert suggestions.status_code == 200
    assert [item["email"] for item in suggestions.get_json()["users"]] == [colleague.email]

    marked = client.post(f"/api/notifications/{row.id}/read")
    assert marked.status_code == 200
    row.reload()
    assert row.read_at is not None
    current = client.get("/api/notifications").get_json()
    assert current["unread_count"] == 0
    assert current["notifications"] == []
    assert current["history_count"] == 1

    history = client.get("/api/notifications?view=history").get_json()
    assert history["notifications"][0]["id"] == str(row.id)
    assert history["notifications"][0]["lifecycle_reason"] == "read"
    assert client.get("/api/notifications?view=unknown").status_code == 400

    other = _user("other-inbox@example.com", viewer)
    _login(client, other)
    assert client.post(f"/api/notifications/{row.id}/read").status_code == 404


def test_markup_thread_mentions_and_uploader_notifications(client):
    viewer = Role(
        name="notification_markup_viewer",
        permissions=[
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "parts.read_unreleased",
            "markups.moderate",
            "markups.write",
        ],
    ).save()
    actor = _user("markup-actor@example.com", viewer)
    mentioned = _user("markup-mentioned@example.com", viewer)
    uploader = _user("markup-uploader@example.com", viewer)
    part = Part(
        part_number="NOTIFY-200",
        revision="A",
        description="Markup notification part",
        attrs={"uploaded_by": uploader.email},
    ).save()
    drawing = PartFile(
        part_number=part.part_number,
        revision="A",
        ext_group="png",
        ext="png",
        is_dwg=True,
        rel_path="drawings/NOTIFY-200_DWG.png",
        path="C:/store/drawings/NOTIFY-200_DWG.png",
        sha256="notify-markup-sha",
        size=123.0,
    ).save()
    _login(client, actor)
    canvas = {
        "version": "7.4.0",
        "objects": [{"type": "Rect", "tmObjectId": "obj-1", "left": 10, "top": 10, "width": 20, "height": 20}],
    }
    saved = client.put(
        f"/api/parts/{part.part_number}/drawing-markups",
        json={"rev": "A", "source_file_id": str(drawing.id), "expected_version": 0, "canvas_json": canvas},
    )
    assert saved.status_code == 200
    created = client.post(
        f"/api/parts/{part.part_number}/drawing-markups/threads",
        json={
            "rev": "A",
            "source_file_id": str(drawing.id),
            "object_ids": ["obj-1"],
            "title": "Check dimension",
            "priority": "high",
            "message": "Please review @markup-mentioned@example.com 🚨",
        },
    )
    assert created.status_code == 201
    thread_id = created.get_json()["threads"][0]["id"]
    assert UserNotification.objects(recipient=mentioned, kind="mention").count() == 1
    assert UserNotification.objects(recipient=uploader, kind="part_review").count() == 1

    _login(client, mentioned)
    current = client.get("/api/notifications").get_json()
    assert current["current_count"] == 1
    assert current["notifications"][0]["thread_id"] == thread_id

    _login(client, actor)
    resolved = client.patch(
        f"/api/parts/{part.part_number}/drawing-markups/threads/{thread_id}",
        json={"rev": "A", "source_file_id": str(drawing.id), "action": "resolve"},
    )
    assert resolved.status_code == 200

    _login(client, mentioned)
    assert client.get("/api/notifications").get_json()["current_count"] == 0
    history = client.get("/api/notifications?view=history").get_json()
    assert history["history_count"] == 1
    assert {row["lifecycle_reason"] for row in history["notifications"]} == {"resolved"}


def test_mention_directory_requires_comment_authority(client):
    """Mention autocomplete must not expose the staff directory to portals."""

    from app.services.standard_roles import STANDARD_ROLES

    def _standard(slug):
        definition = STANDARD_ROLES[slug]
        return Role(
            name=slug,
            display_name=definition.display_name,
            permissions=list(definition.permissions),
        ).save()

    Part(part_number="MENTION-SCOPE", revision="", attrs={"approved": "yes"}).save()
    _user("engineer@example.com", _standard("engineering"))
    portal = _user("buyer@customer.example.com", _standard("customer"))

    _login(client, portal)
    denied = client.get("/api/users/mentionable?q=engineer&pn=MENTION-SCOPE&rev=")
    assert denied.status_code == 403
    assert "engineer@example.com" not in denied.get_data(as_text=True)


def test_home_notifications_show_only_latest_open_comment_and_keep_history(client):
    viewer = Role(
        name="notification_lifecycle_viewer",
        permissions=[
            "comments.read",
            "parts.read",
            "parts.read_unreleased",
        ],
    ).save()
    user = _user("lifecycle@example.com", viewer)
    Part(part_number="LIFE-100", revision="A", description="Lifecycle part").save()
    PartAnnotation(
        part_number="LIFE-100",
        revision="A",
        comments=[
            {"id": "open-1", "text": "Still needs work", "status": "open"},
            {"id": "resolved-1", "text": "Already handled", "status": "resolved"},
        ],
    ).save()
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    deleted = UserNotification(
        recipient=user,
        kind="mention",
        title="Deleted comment",
        url="/ui/part/LIFE-100?rev=A&tab=reviews",
        part_number="LIFE-100",
        revision="A",
        comment_id="deleted-1",
        created_at=started_at,
    ).save()
    resolved = UserNotification(
        recipient=user,
        kind="mention",
        title="Resolved comment",
        url="/ui/part/LIFE-100?rev=A&tab=reviews",
        part_number="LIFE-100",
        revision="A",
        comment_id="resolved-1",
        created_at=started_at + timedelta(minutes=1),
    ).save()
    previous_open = UserNotification(
        recipient=user,
        kind="part_review",
        title="Earlier open activity",
        url="/ui/part/LIFE-100?rev=A&tab=reviews",
        part_number="LIFE-100",
        revision="A",
        comment_id="open-1",
        created_at=started_at + timedelta(minutes=2),
    ).save()
    latest_open = UserNotification(
        recipient=user,
        kind="thread_update",
        title="Latest open activity",
        url="/ui/part/LIFE-100?rev=A&tab=reviews",
        part_number="LIFE-100",
        revision="A",
        comment_id="open-1",
        created_at=started_at + timedelta(minutes=3),
    ).save()
    # Simulate records created before lifecycle fields existed.
    UserNotification._get_collection().update_many(
        {"recipient": user.id},
        {"$unset": {"lifecycle": "", "lifecycle_reason": ""}},
    )
    _login(client, user)

    current = client.get("/api/notifications?view=current&limit=50").get_json()
    assert current["current_count"] == 1
    assert current["history_count"] == 3
    assert [row["id"] for row in current["notifications"]] == [str(latest_open.id)]

    marked = client.post(f"/api/notifications/{latest_open.id}/read")
    assert marked.status_code == 200
    still_current = client.get("/api/notifications?view=current").get_json()
    assert still_current["unread_count"] == 0
    assert [row["id"] for row in still_current["notifications"]] == [str(latest_open.id)]

    history = client.get("/api/notifications?view=history&limit=50").get_json()
    reasons = {row["id"]: row["lifecycle_reason"] for row in history["notifications"]}
    assert reasons == {
        str(previous_open.id): "previous_activity",
        str(resolved.id): "resolved",
        str(deleted.id): "deleted",
    }


def test_comment_resolve_reopen_and_delete_move_home_notifications(client):
    moderator_role = Role(
        name="notification_lifecycle_moderator",
        permissions=[
            "comments.moderate",
            "comments.read",
            "parts.read",
            "parts.read_unreleased",
        ],
    ).save()
    moderator = _user("moderator@example.com", moderator_role)
    recipient = _user("comment-owner@example.com", moderator_role)
    part = Part(part_number="LIFE-200", revision="A", description="Status changes").save()
    PartAnnotation(
        part_number=part.part_number,
        revision="A",
        comments=[
            {
                "id": "comment-200",
                "author": recipient.email,
                "text": "Check this item",
                "status": "open",
            }
        ],
    ).save()
    original = UserNotification(
        recipient=recipient,
        kind="part_review",
        title="New comment",
        url="/ui/part/LIFE-200?rev=A&tab=reviews",
        part_number="LIFE-200",
        revision="A",
        comment_id="comment-200",
        lifecycle="current",
        lifecycle_reason="open",
    ).save()

    _login(client, moderator)
    resolved = client.post(
        "/api/parts/LIFE-200/comments/status",
        json={"rev": "A", "id": "comment-200", "status": "resolved"},
    )
    assert resolved.status_code == 200

    _login(client, recipient)
    assert client.get("/api/notifications").get_json()["notifications"] == []
    resolved_history = client.get("/api/notifications?view=history").get_json()
    assert resolved_history["history_count"] == 2
    assert {row["lifecycle_reason"] for row in resolved_history["notifications"]} == {"resolved"}

    _login(client, moderator)
    reopened = client.post(
        "/api/parts/LIFE-200/comments/status",
        json={"rev": "A", "id": "comment-200", "status": "open"},
    )
    assert reopened.status_code == 200

    _login(client, recipient)
    reopened_current = client.get("/api/notifications").get_json()
    assert reopened_current["current_count"] == 1
    assert reopened_current["notifications"][0]["title"].endswith("was open")

    _login(client, moderator)
    deleted = client.post(
        "/api/parts/LIFE-200/comments/delete",
        json={"rev": "A", "id": "comment-200"},
    )
    assert deleted.status_code == 200

    _login(client, recipient)
    assert client.get("/api/notifications").get_json()["current_count"] == 0
    deleted_history = client.get("/api/notifications?view=history").get_json()
    assert deleted_history["history_count"] == 4
    assert {row["lifecycle_reason"] for row in deleted_history["notifications"]} == {"deleted"}
    assert UserNotification.objects(id=original.id).first() is not None


def test_notification_for_part_outside_current_scope_is_not_disclosed(client):
    viewer = Role(
        name="notification_no_comment_access",
        permissions=["parts.read", "parts.read_unreleased"],
    ).save()
    user = _user("no-comments@example.com", viewer)
    Part(part_number="LIFE-300", revision="A").save()
    PartAnnotation(
        part_number="LIFE-300",
        revision="A",
        comments=[{"id": "private-comment", "text": "Do not leak", "status": "open"}],
    ).save()
    UserNotification(
        recipient=user,
        kind="mention",
        title="Private comment",
        body="Do not leak",
        url="/ui/part/LIFE-300?rev=A&tab=reviews",
        part_number="LIFE-300",
        revision="A",
        comment_id="private-comment",
        lifecycle="current",
    ).save()
    _login(client, user)

    current = client.get("/api/notifications").get_json()
    history = client.get("/api/notifications?view=history").get_json()
    assert current["notifications"] == []
    assert history["notifications"] == []
    assert "Do not leak" not in client.get("/api/notifications?view=all").get_data(as_text=True)


def test_home_template_has_collapsed_notification_history_control():
    source = Path("app/templates/home.html").read_text(encoding="utf-8")

    assert 'id="accountNotificationsHistoryToggle"' in source
    assert 'aria-controls="accountNotificationHistory"' in source
    assert 'id="accountNotificationHistory" class="mt-3" hidden' in source
    assert "/api/notifications?view=current&limit=50" in source
    assert "/api/notifications?view=history&limit=50" in source


def test_customer_resolving_their_own_comment_clears_their_own_queue(client):
    """Issue #99 end to end.

    Codex's lifecycle work drops resolved conversations out of the queue, but a
    customer held no comments.moderate and so could never resolve anything -
    the queue had no way to empty. This is the whole round trip for the role
    that was stuck, in one test.
    """
    from app.services.standard_roles import STANDARD_ROLES

    role = Role(
        name="issue99-customer-queue",
        permissions=[*STANDARD_ROLES["customer"].permissions, "parts.read_unreleased"],
    ).save()
    customer = _user("clive@example.com", role)
    Part(part_number="LIFE-300", revision="A", description="Customer review").save()
    PartAnnotation(
        part_number="LIFE-300",
        revision="A",
        comments=[
            {
                "id": "comment-300",
                "author": customer.email,
                "text": "Please confirm the hole spacing",
                "status": "open",
            }
        ],
    ).save()
    UserNotification(
        recipient=customer,
        kind="part_review",
        title="New comment",
        url="/ui/part/LIFE-300?rev=A&tab=reviews",
        part_number="LIFE-300",
        revision="A",
        comment_id="comment-300",
        lifecycle="current",
        lifecycle_reason="open",
    ).save()

    _login(client, customer)
    assert len(client.get("/api/notifications").get_json()["notifications"]) == 1

    resolved = client.post(
        "/api/parts/LIFE-300/comments/status",
        json={"rev": "A", "id": "comment-300", "status": "resolved"},
    )
    assert resolved.status_code == 200

    current = client.get("/api/notifications").get_json()
    assert current["notifications"] == []
    assert current["current_count"] == 0

    history = client.get("/api/notifications?view=history").get_json()
    assert {row["lifecycle_reason"] for row in history["notifications"]} == {"resolved"}
