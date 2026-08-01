from app.models.auth import Role


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def test_help_page_missing_content(client, app, user, tmp_path):
    role = Role(name="viewer", permissions=[
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
        ]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    app.config["HELP_STATIC_DIR"] = str(tmp_path)
    resp = client.get("/help")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Help content not generated yet" in body
