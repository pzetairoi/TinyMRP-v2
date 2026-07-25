import uuid

from app.models.artifact import PartFile
from app.models.auth import Role, User
from app.models.part import Part
from app.models.part_annotation import PartAnnotation
from app.models.part_drawing_markup import PartDrawingMarkup
from app.services.parts_delete import delete_part_and_refs


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _make_user(email: str, roles=None):
    return User(
        email=email,
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=roles or [],
    ).save()


def _viewer_user(email="markup-viewer@example.com"):
    role = Role(name=f"viewer-{uuid.uuid4()}", permissions=["items.view"]).save()
    return _make_user(email, [role])


def _make_part(pn="PN-500", rev="A"):
    return Part(
        part_number=pn,
        revision=rev,
        description="Markup Part",
        attrs={"approvedby": "QA Person"},
    ).save()


def _make_drawing(pn="PN-500", rev="A", sha256="a1b2c3", rel="drawings/PN-500_DWG.png"):
    return PartFile(
        part_number=pn,
        revision=rev,
        ext_group="png",
        ext="png",
        is_dwg=True,
        rel_path=rel,
        path=f"C:/store/{rel}",
        sha256=sha256,
        size=1234.0,
    ).save()


def _canvas(*ids, extra_objects=None):
    objects = [
        {
            "type": "Rect",
            "tmObjectId": oid,
            "left": 10,
            "top": 10,
            "width": 60,
            "height": 40,
            "stroke": "#d00000",
            "strokeWidth": 2,
            "fill": "",
        }
        for oid in ids
    ]
    if extra_objects:
        objects.extend(extra_objects)
    return {"version": "7.4.0", "objects": objects}


def _base_url(pn="PN-500"):
    return f"/api/parts/{pn}/drawing-markups"


def _get(client, pf, pn="PN-500", rev="A", fingerprint=None):
    qs = f"rev={rev}&source_file_id={pf.id}"
    if fingerprint:
        qs += f"&source_fingerprint={fingerprint}"
    return client.get(f"{_base_url(pn)}?{qs}")


def _put(client, pf, canvas, expected_version, pn="PN-500", rev="A", fingerprint=None):
    body = {
        "rev": rev,
        "source_file_id": str(pf.id),
        "page_number": 1,
        "expected_version": expected_version,
        "canvas_json": canvas,
    }
    if fingerprint:
        body["source_fingerprint"] = fingerprint
    return client.put(_base_url(pn), json=body)


def _setup(client):
    part = _make_part()
    pf = _make_drawing()
    viewer = _viewer_user()
    _login(client, viewer)
    return part, pf, viewer


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def test_unauthenticated_request_rejected(client):
    part = _make_part()
    pf = _make_drawing()
    resp = _get(client, pf)
    assert resp.status_code in (301, 302, 401)


def test_user_without_part_access_gets_403(client, app):
    part = _make_part()
    pf = _make_drawing()
    # Externally scoped user (customer_viewer) with no jobs/orders -> empty allowlist.
    role = Role(name="customer_viewer", permissions=["items.view"]).save()
    external = _make_user("external@example.com", [role])
    _login(client, external)
    resp = _get(client, pf)
    assert resp.status_code == 403
    assert resp.get_json()["ok"] is False


# ---------------------------------------------------------------------------
# GET / PUT lifecycle
# ---------------------------------------------------------------------------

def test_get_returns_empty_version0_layer_without_writing(client):
    part, pf, viewer = _setup(client)
    resp = _get(client, pf)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["version"] == 0
    assert data["canvas_json"] == {"objects": []}
    assert data["threads"] == []
    assert data["stale_layers_count"] == 0
    assert data["can_edit"] is True
    assert data["source"]["source_file_id"] == str(pf.id)
    assert data["source"]["fingerprint"].startswith("sha256:")
    # Viewing must never persist an empty layer.
    assert PartDrawingMarkup.objects.count() == 0


def test_first_put_creates_version_1(client):
    part, pf, viewer = _setup(client)
    fp = _get(client, pf).get_json()["source"]["fingerprint"]
    resp = _put(client, pf, _canvas("obj-1"), expected_version=0, fingerprint=fp)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["version"] == 1
    assert data["canvas_json"]["objects"][0]["tmObjectId"] == "obj-1"
    assert PartDrawingMarkup.objects.count() == 1


def test_matching_update_increments_version(client):
    part, pf, viewer = _setup(client)
    _put(client, pf, _canvas("obj-1"), expected_version=0)
    resp = _put(client, pf, _canvas("obj-1", "obj-2"), expected_version=1)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["version"] == 2
    assert len(data["canvas_json"]["objects"]) == 2


def test_outdated_expected_version_conflicts_without_overwrite(client):
    part, pf, viewer = _setup(client)
    _put(client, pf, _canvas("obj-1"), expected_version=0)
    _put(client, pf, _canvas("obj-1", "obj-2"), expected_version=1)

    resp = _put(client, pf, _canvas("obj-stomp"), expected_version=1)
    assert resp.status_code == 409
    data = resp.get_json()
    assert data["ok"] is False
    assert data["error"] == "conflict"
    # 409 returns the current server representation, not the rejected payload.
    assert data["version"] == 2
    ids = [o["tmObjectId"] for o in data["canvas_json"]["objects"]]
    assert ids == ["obj-1", "obj-2"]

    doc = PartDrawingMarkup.objects.first()
    assert doc.version == 2
    assert len(doc.canvas_json["objects"]) == 2


def test_source_belonging_to_other_part_rejected(client):
    part, pf, viewer = _setup(client)
    _make_part(pn="PN-OTHER", rev="B")
    other_pf = _make_drawing(pn="PN-OTHER", rev="B", rel="drawings/PN-OTHER_DWG.png", sha256="ffff")
    resp = _put(client, other_pf, _canvas("obj-1"), expected_version=0)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "source_not_found"


def test_preview_png_source_accepted_but_non_png_rejected(client):
    part, pf, viewer = _setup(client)
    # Parts without an exported drawing can be marked up on the preview PNG.
    preview = PartFile(
        part_number="PN-500",
        revision="A",
        ext_group="png",
        ext="png",
        is_dwg=False,
        rel_path="previews/PN-500.png",
        path="C:/store/previews/PN-500.png",
    ).save()
    resp = _put(client, preview, _canvas("obj-1"), expected_version=0)
    assert resp.status_code == 200
    assert resp.get_json()["version"] == 1

    # Non-PNG sources (e.g. the PDF itself) are still refused.
    pdf = PartFile(
        part_number="PN-500",
        revision="A",
        ext_group="pdf",
        ext="pdf",
        is_dwg=False,
        rel_path="pdf/PN-500.pdf",
        path="C:/store/pdf/PN-500.pdf",
    ).save()
    resp = _put(client, pdf, _canvas("obj-1"), expected_version=0)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "source_not_found"


# ---------------------------------------------------------------------------
# Canvas validation
# ---------------------------------------------------------------------------

def test_unsupported_or_dangerous_canvas_json_rejected(client):
    part, pf, viewer = _setup(client)

    bad_type = _canvas(extra_objects=[{"type": "Image", "tmObjectId": "x1"}])
    resp = _put(client, pf, bad_type, expected_version=0)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_canvas"

    bad_key = _canvas(extra_objects=[
        {"type": "Rect", "tmObjectId": "x2", "src": "http://evil.example/x.png"}
    ])
    assert _put(client, pf, bad_key, expected_version=0).status_code == 400

    proto_key = _canvas(extra_objects=[
        {"type": "Rect", "tmObjectId": "x3", "__proto__": {"polluted": True}}
    ])
    assert _put(client, pf, proto_key, expected_version=0).status_code == 400

    embedded_image = _canvas(extra_objects=[
        {"type": "Textbox", "tmObjectId": "x4", "text": "data:image/png;base64,AAAA"}
    ])
    assert _put(client, pf, embedded_image, expected_version=0).status_code == 400

    missing_id = {"version": "7.4.0", "objects": [{"type": "Rect"}]}
    assert _put(client, pf, missing_id, expected_version=0).status_code == 400

    unknown_top_key = {"objects": [], "background": "url(http://evil)"}
    assert _put(client, pf, unknown_top_key, expected_version=0).status_code == 400

    # Nothing was persisted by any of the rejected payloads.
    assert PartDrawingMarkup.objects.count() == 0


def test_excessive_payloads_rejected(client):
    part, pf, viewer = _setup(client)

    too_many = _canvas(*[f"o-{i}" for i in range(501)])
    resp = _put(client, pf, too_many, expected_version=0)
    assert resp.status_code == 413

    long_text = _canvas(extra_objects=[
        {"type": "Textbox", "tmObjectId": "t1", "text": "x" * 5001}
    ])
    assert _put(client, pf, long_text, expected_version=0).status_code == 413

    _put(client, pf, _canvas("obj-1"), expected_version=0)
    resp = client.post(
        f"{_base_url()}/threads",
        json={
            "rev": "A",
            "source_file_id": str(pf.id),
            "object_ids": ["obj-1"],
            "message": "y" * 5001,
        },
    )
    assert resp.status_code == 413


# ---------------------------------------------------------------------------
# Review threads
# ---------------------------------------------------------------------------

def _create_thread(client, pf, object_ids, message="Check this dimension", title="", priority="high"):
    return client.post(
        f"{_base_url()}/threads",
        json={
            "rev": "A",
            "source_file_id": str(pf.id),
            "object_ids": object_ids,
            "title": title,
            "priority": priority,
            "message": message,
        },
    )


def test_thread_requires_valid_object_id(client):
    part, pf, viewer = _setup(client)
    _put(client, pf, _canvas("obj-1"), expected_version=0)

    resp = _create_thread(client, pf, ["missing-object"])
    assert resp.status_code == 400

    resp = _create_thread(client, pf, [])
    assert resp.status_code == 400

    resp = _create_thread(client, pf, ["obj-1"], title="Hole size")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["version"] == 2
    assert len(data["threads"]) == 1
    thread = data["threads"][0]
    assert thread["object_ids"] == ["obj-1"]
    assert thread["title"] == "Hole size"
    assert thread["priority"] == "high"
    assert thread["status"] == "open"
    assert thread["linked"] is True
    assert thread["messages"][0]["text"] == "Check this dimension"


def test_thread_requires_message(client):
    part, pf, viewer = _setup(client)
    _put(client, pf, _canvas("obj-1"), expected_version=0)
    resp = _create_thread(client, pf, ["obj-1"], message="")
    assert resp.status_code == 400


def test_reply_persists(client):
    part, pf, viewer = _setup(client)
    _put(client, pf, _canvas("obj-1"), expected_version=0)
    thread_id = _create_thread(client, pf, ["obj-1"]).get_json()["threads"][0]["id"]

    resp = client.post(
        f"{_base_url()}/threads/{thread_id}/messages",
        json={"rev": "A", "source_file_id": str(pf.id), "text": "Agreed, needs +0.1"},
    )
    assert resp.status_code == 200
    thread = resp.get_json()["threads"][0]
    assert [m["text"] for m in thread["messages"]] == ["Check this dimension", "Agreed, needs +0.1"]
    assert thread["reply_count"] == 1

    doc = PartDrawingMarkup.objects.first()
    assert len(doc.threads[0].messages) == 2


def test_resolve_and_reopen_update_metadata(client):
    part, pf, viewer = _setup(client)
    _put(client, pf, _canvas("obj-1"), expected_version=0)
    thread_id = _create_thread(client, pf, ["obj-1"]).get_json()["threads"][0]["id"]

    resp = client.patch(
        f"{_base_url()}/threads/{thread_id}",
        json={"rev": "A", "source_file_id": str(pf.id), "action": "resolve"},
    )
    assert resp.status_code == 200
    thread = resp.get_json()["threads"][0]
    assert thread["status"] == "resolved"
    assert thread["resolved_by"] == "markup-viewer@example.com"
    assert thread["resolved_at"]

    resp = client.patch(
        f"{_base_url()}/threads/{thread_id}",
        json={"rev": "A", "source_file_id": str(pf.id), "action": "reopen"},
    )
    assert resp.status_code == 200
    thread = resp.get_json()["threads"][0]
    assert thread["status"] == "open"
    assert thread["resolved_by"] == ""
    assert thread["resolved_at"] is None

    resp = client.patch(
        f"{_base_url()}/threads/{thread_id}",
        json={"rev": "A", "source_file_id": str(pf.id), "action": "explode"},
    )
    assert resp.status_code == 400


def test_thread_delete_removes_thread_but_keeps_markup(client):
    part, pf, viewer = _setup(client)
    _put(client, pf, _canvas("obj-1"), expected_version=0)
    thread_id = _create_thread(client, pf, ["obj-1"]).get_json()["threads"][0]["id"]

    resp = client.delete(
        f"{_base_url()}/threads/{thread_id}",
        json={"rev": "A", "source_file_id": str(pf.id)},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["threads"] == []
    # The markup object itself stays on the canvas.
    assert [o["tmObjectId"] for o in data["canvas_json"]["objects"]] == ["obj-1"]

    missing = client.delete(
        f"{_base_url()}/threads/{thread_id}",
        json={"rev": "A", "source_file_id": str(pf.id)},
    )
    assert missing.status_code == 404


def test_identity_and_display_time_fields_returned(client):
    part, pf, viewer = _setup(client)
    _put(client, pf, _canvas("obj-1"), expected_version=0)
    data = _create_thread(client, pf, ["obj-1"]).get_json()
    thread = data["threads"][0]
    assert thread["created_by"] == "markup-viewer@example.com"
    assert thread["created_by_display"]
    assert thread["created_by_profile"]["initials"]
    assert thread["created_at_display"]
    msg = thread["messages"][0]
    assert msg["ts"]
    assert msg["ts_display"]
    assert msg["ts_local"]
    assert msg["author"] == "markup-viewer@example.com"
    assert msg["author_display"]
    assert msg["author_profile"]["initials"]


# ---------------------------------------------------------------------------
# Fingerprint / staleness
# ---------------------------------------------------------------------------

def test_changed_source_never_silently_returns_old_layer(client):
    part, pf, viewer = _setup(client)
    old_fp = _get(client, pf).get_json()["source"]["fingerprint"]
    _put(client, pf, _canvas("obj-1"), expected_version=0, fingerprint=old_fp)

    # Drawing gets replaced: the sha256 changes.
    pf.sha256 = "new-sha-after-replacement"
    pf.save()

    # A stale client submitting the old fingerprint is refused.
    resp = _put(client, pf, _canvas("obj-1"), expected_version=1, fingerprint=old_fp)
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "stale_source"

    # A fresh GET resolves the new fingerprint: empty layer, old layer counted as history.
    resp = _get(client, pf)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["version"] == 0
    assert data["canvas_json"] == {"objects": []}
    assert data["source"]["fingerprint"] != old_fp
    assert data["stale_layers_count"] == 1

    # The historical layer is preserved untouched.
    old_doc = PartDrawingMarkup.objects(source_fingerprint=old_fp).first()
    assert old_doc is not None
    assert old_doc.version == 1


def test_missing_sha256_uses_deterministic_metadata_fingerprint(client):
    part = _make_part(pn="PN-600", rev="")
    pf = _make_drawing(pn="PN-600", rev="", sha256="", rel="drawings/PN-600_DWG.png")
    viewer = _viewer_user("markup-meta@example.com")
    _login(client, viewer)
    resp = client.get(f"/api/parts/PN-600/drawing-markups?rev=&source_file_id={pf.id}")
    assert resp.status_code == 200
    fp1 = resp.get_json()["source"]["fingerprint"]
    fp2 = client.get(f"/api/parts/PN-600/drawing-markups?rev=&source_file_id={pf.id}").get_json()["source"]["fingerprint"]
    assert fp1 == fp2
    assert fp1.startswith("meta:")


# ---------------------------------------------------------------------------
# part_images metadata
# ---------------------------------------------------------------------------

def test_part_images_drawing_rows_expose_safe_metadata(client, app, tmp_path):
    part, pf, viewer = _setup(client)
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    drawing_path = tmp_path / pf.rel_path
    drawing_path.parent.mkdir(parents=True, exist_ok=True)
    drawing_path.write_bytes(b"drawing")
    pf.path = str(drawing_path)
    pf.save()
    resp = client.get("/api/part_images?pn=PN-500&rev=A&mode=drawing")
    assert resp.status_code == 200
    rows = resp.get_json()
    assert len(rows) == 1
    row = rows[0]
    assert row["urls"]
    assert row["revision"] == "A"
    assert row["source_file_id"] == str(pf.id)
    assert row["rel_path"] == "drawings/PN-500_DWG.png"
    assert row["source_fingerprint"].startswith("sha256:")
    assert row["is_dwg"] is True
    assert row["image_urls"]
    # No absolute server paths leak through.
    assert "C:/" not in str(row)

    # Preview rows also expose the metadata (preview-PNG markup fallback) and
    # full-size image URLs that skip the thumbnail.
    preview_path = tmp_path / "previews" / "PN-500.png"
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.write_bytes(b"preview")
    thumbnail_path = tmp_path / "thumbs" / "png" / "PN-500.png"
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    thumbnail_path.write_bytes(b"thumbnail")
    PartFile(
        part_number="PN-500",
        revision="A",
        ext_group="png",
        ext="png",
        is_dwg=False,
        rel_path="previews/PN-500.png",
        path=str(preview_path),
        thumb_rel_path="thumbs/png/PN-500.png",
        sha256="previewsha",
    ).save()
    preview = client.get("/api/part_images?pn=PN-500&rev=A&mode=preview")
    assert preview.status_code == 200
    prows = preview.get_json()
    assert len(prows) == 1
    prow = prows[0]
    assert prow["is_dwg"] is False
    assert prow["source_file_id"]
    assert prow["source_fingerprint"].startswith("sha256:")
    # image_urls skips the thumbnail: it is the full-size file URL only,
    # while urls leads with the thumbnail variant.
    assert prow["image_urls"]
    assert len(prow["urls"]) > len(prow["image_urls"])
    assert prow["image_urls"][0] == prow["urls"][-1]
    assert prow["image_urls"][0] != prow["urls"][0]


# ---------------------------------------------------------------------------
# Deletion + legacy annotation behaviour
# ---------------------------------------------------------------------------

def test_part_delete_removes_markup_documents(client, app):
    part, pf, viewer = _setup(client)
    _put(client, pf, _canvas("obj-1"), expected_version=0)
    assert PartDrawingMarkup.objects.count() == 1

    with app.app_context():
        result = delete_part_and_refs("PN-500", "A")
    assert result["deleted_drawing_markups"] == 1
    assert result["deleted_parts"] == 1
    assert PartDrawingMarkup.objects.count() == 0


def test_existing_notes_and_comments_endpoints_still_work(client):
    part, pf, viewer = _setup(client)
    _put(client, pf, _canvas("obj-1"), expected_version=0)

    note = client.post("/api/parts/PN-500/notes", json={"rev": "A", "notes": "Still fine"})
    assert note.status_code == 200

    comment = client.post("/api/parts/PN-500/comments", json={"rev": "A", "text": "Legacy comment"})
    assert comment.status_code == 200
    assert comment.get_json()["comment"]["text"] == "Legacy comment"

    detail = client.get("/api/part_detail?pn=PN-500&rev=A")
    assert detail.status_code == 200
    body = detail.get_json()
    assert body["part"]["notes"] == "Still fine"
    assert body["comments"][0]["text"] == "Legacy comment"

    annotation = PartAnnotation.objects(part_number="PN-500", revision="A").first()
    assert annotation is not None
    assert annotation.notes == "Still fine"
    assert len(annotation.comments) == 1


def test_legacy_annotation_migration_unchanged_by_markups(client):
    part = Part(
        part_number="PN-700",
        revision="A",
        description="Legacy",
        attrs={"notes": "Imported note", "comments": "Imported comment", "material": "Steel"},
    ).save()
    pf = _make_drawing(pn="PN-700", rev="A", rel="drawings/PN-700_DWG.png", sha256="dd")
    viewer = _viewer_user("markup-legacy@example.com")
    _login(client, viewer)

    resp = client.put(
        "/api/parts/PN-700/drawing-markups",
        json={
            "rev": "A",
            "source_file_id": str(pf.id),
            "expected_version": 0,
            "canvas_json": _canvas("obj-1"),
        },
    )
    assert resp.status_code == 200

    # Markup writes never touch Part.attrs or PartAnnotation.
    part.reload()
    assert part.attrs.get("notes") == "Imported note"
    assert part.attrs.get("comments") == "Imported comment"
    assert PartAnnotation.objects(part_number="PN-700").count() == 0

    # Legacy migration continues to behave as before.
    note = client.post("/api/parts/PN-700/notes", json={"rev": "A", "notes": "migrated"})
    assert note.status_code == 200
    annotation = PartAnnotation.objects(part_number="PN-700", revision="A").first()
    assert annotation is not None
    assert annotation.notes == "migrated"
    part.reload()
    assert part.attrs.get("material") == "Steel"
