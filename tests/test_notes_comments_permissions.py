from app.models.auth import Role, User
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
    assert part.attrs.get("notes") == "hello"

    editor = _make_user("editor@example.com")
    editor.roles = [editor_role]
    editor.save()
    _login(client, editor)

    resp2 = client.post(f"/api/parts/{part.part_number}/notes", json={"notes": "updated"})
    assert resp2.status_code == 200
    part.reload()
    assert part.attrs.get("notes") == "updated"


def test_notes_and_comments_preserve_attrs_and_are_searchable(client, user):
    viewer_role = Role(name="viewer_notes", permissions=["items.view"]).save()
    user.roles = [viewer_role]
    user.save()
    _login(client, user)

    part = Part(
        part_number="PN-901",
        revision="A",
        description="Searchable Part",
        attrs={"material": "Steel", "finish": "Paint"},
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
    assert part.attrs.get("material") == "Steel"
    assert part.attrs.get("finish") == "Paint"
    assert part.attrs.get("notes") == "Needs fixture before release"
    assert "QA review" in (part.attrs.get("comments_search") or "")

    detail_resp = client.get(f"/api/part_detail?pn={part.part_number}&rev=A")
    assert detail_resp.status_code == 200
    detail = detail_resp.get_json()
    assert detail["part"]["field_values"]["material"] == "Steel"

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
    assert any(row["part_number"] == "PN-901" for row in rows)

    list_resp2 = client.post(
        "/api/parts_lazy",
        json={
            "first": 0,
            "rows": 25,
            "filters": {
                "global": {"value": "QA review"},
            },
        },
    )
    assert list_resp2.status_code == 200
    rows2 = list_resp2.get_json()["data"]
    assert any(row["part_number"] == "PN-901" for row in rows2)
