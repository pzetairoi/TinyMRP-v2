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
    assert 'id="helpScope"' in body
    assert "Help &amp; documentation" in body


def test_help_keeps_user_guidance_first_and_excludes_developer_material(client, app, user):
    """Operator references are reachable without publishing developer records."""

    _admin(user)
    _login(client, user)

    body = client.get("/help").get_data(as_text=True)

    assert '<option value="user-guide" selected>User guide</option>' in body
    assert '<option value="all">All available documentation</option>' in body
    for section in (
        "Installation &amp; operations",
        "Product information",
    ):
        assert section in body
    for developer_only in (
        "History &amp; evidence",
        "Engineering &amp; reference",
        "Security &amp; governance",
        "Security risk-acceptance template",
    ):
        assert developer_only not in body

    assert 'data-help-source="docs/deployment/09-local-development.md"' not in body


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


def test_help_links_to_the_practice_pack_download(client, app, user):
    """The exercise names files an operator cannot get without this link."""

    _admin(user)
    _login(client, user)

    body = client.get("/help").get_data(as_text=True)
    assert 'href="/help/practice-packs.zip"' in body


def test_practice_pack_download_requires_login(client):
    resp = client.get("/help/practice-packs.zip")
    assert resp.status_code in (302, 401)


def test_practice_pack_download_is_a_working_exercise_bundle(client, app, user):
    """Every file the exercise table and README refer to must actually be in it."""

    import io
    import zipfile

    _admin(user)
    _login(client, user)

    resp = client.get("/help/practice-packs.zip")
    assert resp.status_code == 200
    assert resp.mimetype == "application/zip"
    assert "attachment" in (resp.headers.get("Content-Disposition") or "")

    archive = zipfile.ZipFile(io.BytesIO(resp.data))
    names = set(archive.namelist())
    for step in range(1, 12):
        assert any(name.startswith(f"{step:02d}_") for name in names), step
    assert "README.md" in names
    assert "index.json" in names
    assert any(name.startswith("out_of_band/") for name in names)


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
