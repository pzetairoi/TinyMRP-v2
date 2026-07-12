from app.models.auth import Role, User
from app.models.artifact import PartFile
from app.models.notification import UserNotification
from app.models.part import Part
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
    viewer = Role(name="notification_viewer", permissions=["items.view"]).save()
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
    viewer = Role(name="notification_api_viewer", permissions=["items.view"]).save()
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
    Part(part_number="MENTION-1", revision="", description="Mention scope").save()
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
    assert client.get("/api/notifications").get_json()["unread_count"] == 0

    other = _user("other-inbox@example.com", viewer)
    _login(client, other)
    assert client.post(f"/api/notifications/{row.id}/read").status_code == 404


def test_markup_thread_mentions_and_uploader_notifications(client):
    viewer = Role(name="notification_markup_viewer", permissions=["items.view"]).save()
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
    assert UserNotification.objects(recipient=mentioned, kind="mention").count() == 1
    assert UserNotification.objects(recipient=uploader, kind="part_review").count() == 1
