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


def _admin(user):
    role = Role(name="help_admin", permissions=["parts.read"]).save()
    user.roles = [role]
    user.save()
    return user


def test_help_page_renders_collapsible_sections(client, app, user):
    """The built help must fold into sections rather than one long wall."""

    _admin(user)
    _login(client, user)

    body = client.get("/help").get_data(as_text=True)

    assert '<details class="help-section"' in body
    assert 'class="help-chapter"' in body
    # Search and the expand/collapse controls drive the whole page.
    assert 'id="helpSearch"' in body
    assert 'id="helpExpand"' in body


def test_help_covers_the_features_users_ask_about(client, app, user):
    """Guards against the built help drifting away from the shipped UI."""

    _admin(user)
    _login(client, user)

    body = client.get("/help").get_data(as_text=True)

    for topic in (
        "Approved vs draft",
        "Doc Packs",
        "Roles and Permissions",
        "Troubleshooting",
        # Rules that are easy to trip over and must stay documented.
        "parts.read_unreleased",
        "imports.override_approved",
        # The import policy reference, which the Import page links straight at.
        "Import: what each choice does",
        "What counts as approved",
        "Import FAQ",
    ):
        assert topic in body, topic


def test_help_import_chapter_anchors_match_the_links_into_it(client, app, user):
    """The Import page deep-links into this chapter, so its anchors must exist."""

    _admin(user)
    _login(client, user)

    body = client.get("/help").get_data(as_text=True)

    for anchor in ("import-what-each-choice-does", "what-counts-as-approved"):
        assert f'id="{anchor}"' in body, anchor


def test_help_screenshots_are_present_and_captioned(client, app, user):
    """A screenshot without a caption does not tell the reader what to notice."""

    from pathlib import Path

    _admin(user)
    _login(client, user)

    body = client.get("/help").get_data(as_text=True)
    images = Path(app.static_folder) / "help" / "img"

    assert '<figure class="help-figure">' in body
    for name in ("inventory", "import", "roles", "customer-portal"):
        assert f"/static/help/img/{name}.png" in body, name
        assert (images / f"{name}.png").is_file(), name
    # Every figure carries a caption element.
    assert body.count('<figure class="help-figure">') == body.count(
        '<figcaption class="help-figure-caption">'
    )
