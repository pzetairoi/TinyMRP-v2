from app.models.auth import Role, User
from app.models.part_annotation import PartAnnotation
from app.models.part import Part


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _make_user(email: str):
    user = User(email=email, password="test", active=True, fs_uniquifier=email)
    user.save()
    return user


def test_notes_update_permissions(client, user):
    viewer_role = Role(name="viewer", permissions=["items.view"]).save()
    editor_role = Role(name="editor", permissions=["items.view", "items.edit"]).save()

    part = Part(part_number="PN-900", revision="", description="Notes Part").save()

    user.roles = [viewer_role]
    user.save()
    _login(client, user)

    resp = client.post(f"/api/parts/{part.part_number}/notes", json={"notes": "hello"})
    assert resp.status_code == 200
    part.reload()
    annotation = PartAnnotation.objects(part_number=part.part_number, revision="").first()
    assert annotation is not None
    assert annotation.notes == "hello"
    assert dict(part.attrs or {}).get("notes") in (None, "")
    assert part.notes_search == "hello"

    editor = _make_user("editor@example.com")
    editor.roles = [editor_role]
    editor.save()
    _login(client, editor)

    resp2 = client.post(f"/api/parts/{part.part_number}/notes", json={"notes": "updated"})
    assert resp2.status_code == 200
    part.reload()
    annotation.reload()
    assert annotation.notes == "updated"
    assert dict(part.attrs or {}).get("notes") in (None, "")
    assert part.notes_search == "updated"


def test_notes_and_comments_preserve_attrs_and_keep_search_indexes(client, user):
    viewer_role = Role(name="viewer_notes", permissions=["items.view"]).save()
    user.roles = [viewer_role]
    user.save()
    _login(client, user)

    part = Part(
        part_number="PN-901",
        revision="A",
        description="Searchable Part",
        attrs={
            "material": "Steel",
            "finish": "Paint",
            "approvedby": "QA Person",
            "notes": "Imported supplier note",
            "comments": "Imported drawing comment",
        },
    ).save()

    note_resp = client.post(
        f"/api/parts/{part.part_number}/notes",
        json={"rev": "A", "notes": "Needs fixture before release"},
    )
    assert note_resp.status_code == 200

    comment_resp = client.post(
        f"/api/parts/{part.part_number}/comments",
        json={"rev": "A", "text": "Waiting for QA review"},
    )
    assert comment_resp.status_code == 200

    part.reload()
    annotation = PartAnnotation.objects(part_number=part.part_number, revision="A").first()
    assert annotation is not None
    assert annotation.notes == "Needs fixture before release"
    assert len(annotation.comments) == 1
    assert part.attrs.get("material") == "Steel"
    assert part.attrs.get("finish") == "Paint"
    assert part.attrs.get("notes") == "Imported supplier note"
    assert part.attrs.get("comments") == "Imported drawing comment"
    assert part.notes_search == "Needs fixture before release"
    assert "QA review" in (part.comments_search or "")

    detail_resp = client.get(f"/api/part_detail?pn={part.part_number}&rev=A")
    assert detail_resp.status_code == 200
    detail = detail_resp.get_json()
    assert detail["part"]["field_values"]["material"] == "Steel"
    assert detail["part"]["notes"] == "Needs fixture before release"
    assert "notes" not in detail["part"]["attributes"]
    assert "comments" not in detail["part"]["attributes"]
    assert detail["comments"][0]["text"] == "Waiting for QA review"

    list_resp = client.post(
        "/api/parts_lazy",
        json={
            "first": 0,
            "rows": 25,
            "filters": {
                "global": {"value": "fixture"},
            },
        },
    )
    assert list_resp.status_code == 200
    rows = list_resp.get_json()["data"]
    assert [row["part_number"] for row in rows] == ["PN-901"]


def test_comment_priority_id_and_delete_endpoint(client, user):
    viewer_role = Role(name="viewer_comment_delete", permissions=["items.view"]).save()
    user.roles = [viewer_role]
    user.save()
    _login(client, user)

    part = Part(part_number="PN-902", revision="B", description="Comment actions").save()
    first = client.post(
        f"/api/parts/{part.part_number}/comments",
        json={"rev": "B", "text": "Critical drawing issue", "priority": "high"},
    )
    second = client.post(
        f"/api/parts/{part.part_number}/comments",
        json={"rev": "B", "text": "Unranked note"},
    )
    assert first.status_code == 200
    assert second.status_code == 200

    first_comment = first.get_json()["comment"]
    assert first_comment["id"]
    assert first_comment["priority"] == "high"
    assert second.get_json()["comment"]["priority"] == ""

    deleted = client.post(
        f"/api/parts/{part.part_number}/comments/delete",
        json={"rev": "B", "id": first_comment["id"]},
    )
    assert deleted.status_code == 200
    remaining = deleted.get_json()["comments"]
    assert [row["text"] for row in remaining] == ["Unranked note"]

    part.reload()
    annotation = PartAnnotation.objects(part_number=part.part_number, revision="B").first()
    assert annotation is not None
    assert [row["text"] for row in annotation.comments] == ["Unranked note"]
    assert "Critical drawing issue" not in (part.comments_search or "")
    assert "Unranked note" in (part.comments_search or "")

    missing = client.post(
        f"/api/parts/{part.part_number}/comments/delete",
        json={"rev": "B", "id": first_comment["id"]},
    )
    assert missing.status_code == 404


def test_parts_table_exposes_and_filters_pending_review_severity(client, user):
    viewer_role = Role(name="viewer_review_filter", permissions=["items.view"]).save()
    user.roles = [viewer_role]
    user.save()
    _login(client, user)

    high_part = Part(
        part_number="REVIEW-HIGH",
        revision="A",
        description="Needs review",
        attrs={"approvedby": "QA Person"},
    ).save()
    clear_part = Part(
        part_number="REVIEW-CLEAR",
        revision="A",
        description="Ready",
        attrs={"approvedby": "QA Person"},
    ).save()
    created = client.post(
        f"/api/parts/{high_part.part_number}/comments",
        json={"rev": "A", "text": "Dimension needs confirmation", "priority": "high"},
    )
    assert created.status_code == 200

    pending = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {"pending_reviews": {"value": "pending"}}},
    )
    assert pending.status_code == 200
    pending_rows = pending.get_json()["data"]
    assert [row["part_number"] for row in pending_rows] == ["REVIEW-HIGH"]
    assert pending_rows[0]["pending_review_count"] == 1
    assert pending_rows[0]["pending_review_severity"] == "high"
    assert pending_rows[0]["has_pending_reviews"] is True
    assert "comments" not in pending_rows[0]

    high = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {"pending_reviews": {"value": "high"}}},
    )
    assert [row["part_number"] for row in high.get_json()["data"]] == ["REVIEW-HIGH"]

    comment_id = created.get_json()["comment"]["id"]
    resolved = client.post(
        f"/api/parts/{high_part.part_number}/comments/status",
        json={"rev": "A", "id": comment_id, "status": "resolved"},
    )
    assert resolved.status_code == 200
    assert resolved.get_json()["comment"]["status"] == "resolved"

    clear = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {"pending_reviews": {"value": "none"}}},
    )
    assert [row["part_number"] for row in clear.get_json()["data"]] == [clear_part.part_number, high_part.part_number]

    reopened = client.post(
        f"/api/parts/{high_part.part_number}/comments/status",
        json={"rev": "A", "id": comment_id, "status": "open"},
    )
    assert reopened.status_code == 200
    deleted = client.post(
        f"/api/parts/{high_part.part_number}/comments/delete",
        json={"rev": "A", "id": comment_id},
    )
    assert deleted.status_code == 200
    high_part.reload()
    assert high_part.pending_review_count == 0
    assert high_part.pending_review_severity == ""


def test_comment_reply_and_priority_edit_endpoints(client, user):
    from app.models.notification import UserNotification

    viewer_role = Role(name="viewer_reply", permissions=["items.view"]).save()
    user.roles = [viewer_role]
    user.save()
    _login(client, user)

    part = Part(
        part_number="PN-905",
        revision="A",
        description="Reply Part",
        attrs={"approvedby": "QA Person"},
    ).save()
    created = client.post(
        f"/api/parts/{part.part_number}/comments",
        json={"rev": "A", "text": "Base comment", "priority": "low"},
    )
    assert created.status_code == 200
    comment_id = created.get_json()["comment"]["id"]

    # Replies persist and are returned with identity/display fields.
    reply = client.post(
        f"/api/parts/{part.part_number}/comments/reply",
        json={"rev": "A", "id": comment_id, "text": "A reply"},
    )
    assert reply.status_code == 200
    payload = reply.get_json()["comment"]
    assert payload["reply_count"] == 1
    assert payload["replies"][0]["text"] == "A reply"
    assert payload["replies"][0]["author"] == user.email
    assert payload["replies"][0]["ts_display"]
    assert payload["replies"][0]["author_profile"]["initials"]

    missing = client.post(
        f"/api/parts/{part.part_number}/comments/reply",
        json={"rev": "A", "id": "nope", "text": "x"},
    )
    assert missing.status_code == 404

    # Replies survive round-trips through part_detail and are searchable.
    detail = client.get(f"/api/part_detail?pn={part.part_number}&rev=A")
    assert detail.get_json()["comments"][0]["replies"][0]["text"] == "A reply"
    part.reload()
    assert "A reply" in (part.comments_search or "")

    # Importance can be edited after creation...
    updated = client.post(
        f"/api/parts/{part.part_number}/comments/priority",
        json={"rev": "A", "id": comment_id, "priority": "high"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["comment"]["priority"] == "high"

    # ...cleared again...
    cleared = client.post(
        f"/api/parts/{part.part_number}/comments/priority",
        json={"rev": "A", "id": comment_id, "priority": ""},
    )
    assert cleared.status_code == 200
    assert cleared.get_json()["comment"]["priority"] == ""

    invalid = client.post(
        f"/api/parts/{part.part_number}/comments/priority",
        json={"rev": "A", "id": comment_id, "priority": "urgent"},
    )
    assert invalid.status_code == 400

    # Changing your own comment's importance never notifies yourself.
    assert UserNotification.objects(kind="comment_changed").count() == 0

    # A different user editing the importance notifies the comment author.
    editor = _make_user("importance-editor@example.com")
    editor.roles = [viewer_role]
    editor.save()
    _login(client, editor)
    other_edit = client.post(
        f"/api/parts/{part.part_number}/comments/priority",
        json={"rev": "A", "id": comment_id, "priority": "normal"},
    )
    assert other_edit.status_code == 200
    notes = list(UserNotification.objects(kind="comment_changed"))
    assert len(notes) == 1
    assert notes[0].recipient.email == user.email
    assert "Importance changed" in notes[0].title
