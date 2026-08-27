"""What a public share link exposes, level by level.

The blank-image defect these start from was invisible: a `.only()` projection
that omitted `ext_group` left the attribute None, the scope guard read that as
"not a shareable type", and every shared preview came back empty with no error
anywhere. Nothing in the response said a file had been withheld.
"""

import uuid

from app.models.artifact import PartFile
from app.models.auth import Role, User
from app.models.part import Part
from app.models.part_share import PartShareLink
from app.services.permissions import PERMISSION_REGISTRY


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _admin(client, email):
    role = (
        Role.objects(name="administrator").first()
        or Role(name="administrator", permissions=sorted(PERMISSION_REGISTRY)).save()
    )
    user = User(
        email=email,
        password="test-password-123",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=[role],
    ).save()
    _login(client, user)
    return user


def _grant_fixture(app, tmp_path, part_number):
    """One part carrying one file of every group a share level can gate."""

    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILE_SOURCES"] = [{"local_root": str(tmp_path)}]
    part = Part(part_number=part_number, revision="A", description="Grants").save()
    written = {}
    for group, is_dwg in (
        ("png", False),
        ("png", True),
        ("ply", False),
        ("pdf", False),
        ("step", False),
        ("dxf", False),
        ("datasheet", False),
    ):
        name = group + ("-dwg" if is_dwg else "")
        rel = f"{name}/{part_number}.{group}"
        abs_path = tmp_path / rel
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(name.encode())
        written[name] = PartFile(
            part_number=part.part_number,
            revision=part.revision,
            ext_group=group,
            ext=group,
            is_dwg=is_dwg,
            rel_path=rel,
            path=str(abs_path),
        ).save()
    return part, written


def _visible_groups(public_client, created, part):
    """Which file groups a token actually reaches, read off the public payload."""

    detail = public_client.get(
        f"/api/share/part/{created['share_id']}/{created['share_token']}"
        f"/part_detail?pn={part.part_number}&rev={part.revision}"
    )
    assert detail.status_code == 200, detail.get_data(as_text=True)
    payload = detail.get_json()
    groups = {group for group, rows in payload["files"].items() if rows}
    if payload["images"]:
        groups.add("png")
    if payload["drawing_urls"]:
        groups.add("png-dwg")
    return groups


def test_share_levels_gate_file_groups(client, app, tmp_path):
    """Preview is the floor - images and the 3D mesh - and levels add to it."""

    _admin(client, "levels@example.com")
    part, _files = _grant_fixture(app, tmp_path, "PN-GRANT")
    public_client = app.test_client()

    def groups_for(**payload):
        resp = client.post(
            f"/api/parts/{part.part_number}/shares",
            json={"rev": part.revision, "expires_in_days": 30, **payload},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        return _visible_groups(public_client, resp.get_json(), part)

    assert groups_for(tier="preview") == {"png", "ply"}
    assert groups_for(tier="review") == {"png", "png-dwg", "ply", "pdf", "datasheet"}
    assert groups_for(tier="supplier") == {
        "png",
        "png-dwg",
        "ply",
        "pdf",
        "step",
        "dxf",
        "datasheet",
    }

    # A per-flag override wins over the level it started from, in both
    # directions - that is what makes "Customise" more than decoration.
    assert groups_for(tier="preview", allow_datasheets=True) == {
        "png",
        "ply",
        "datasheet",
    }
    assert groups_for(tier="supplier", allow_neutral_cad=False) == {
        "png",
        "png-dwg",
        "ply",
        "pdf",
        "datasheet",
    }


def test_preview_level_withholds_the_drawing_png(client, app, tmp_path):
    """A drawing export is ext_group png too, so only is_dwg separates them."""

    _admin(client, "dwgpng@example.com")
    part, files = _grant_fixture(app, tmp_path, "PN-DWGPNG")
    resp = client.post(
        f"/api/parts/{part.part_number}/shares",
        json={"rev": part.revision, "expires_in_days": 30, "tier": "preview"},
    )
    created = resp.get_json()
    public_client = app.test_client()
    prefix = f"/share/part/{created['share_id']}/{created['share_token']}"
    with app.app_context():
        from app.services.files_access import file_token_for

        preview_token = file_token_for(files["png"])
        drawing_token = file_token_for(files["png-dwg"])

    assert public_client.get(f"{prefix}/files/{preview_token}").status_code == 200
    assert public_client.get(f"{prefix}/files/{drawing_token}").status_code == 404

    drawings = public_client.get(
        f"/api/share/part/{created['share_id']}/{created['share_token']}"
        f"/part_images?pn={part.part_number}&rev={part.revision}&mode=drawing"
    )
    assert drawings.get_json() == []


def test_levels_added_later_grandfather_onto_older_links(client, app, tmp_path):
    """A link already in someone's inbox must not start showing less.

    The level fields did not exist when the first shares were issued, so those
    documents carry no such key. Reading that absence as "denied" would strip a
    supplier's STEP file out of a URL they had already been sent.
    """
    _admin(client, "legacy@example.com")
    part, _files = _grant_fixture(app, tmp_path, "PN-LEGACY")
    resp = client.post(
        f"/api/parts/{part.part_number}/shares",
        json={"rev": part.revision, "expires_in_days": 30, "tier": "preview"},
    )
    created = resp.get_json()
    public_client = app.test_client()
    assert _visible_groups(public_client, created, part) == {"png", "ply"}

    share = PartShareLink.objects(id=created["share_id"]).first()
    PartShareLink._get_collection().update_one(
        {"_id": share.id},
        {
            "$unset": {
                "allow_drawings": "",
                "allow_neutral_cad": "",
                "allow_datasheets": "",
                "allow_all_files": "",
            }
        },
    )
    assert _visible_groups(public_client, created, part) == {
        "png",
        "png-dwg",
        "ply",
        "pdf",
        "step",
        "dxf",
        "datasheet",
    }


def test_docpack_cannot_package_a_group_the_share_withholds(client, app, tmp_path):
    """A fabrication pack forces dxf/step/pdf without ever naming them."""

    _admin(client, "packgrants@example.com")
    part, _files = _grant_fixture(app, tmp_path, "PN-PACKGRANT")
    resp = client.post(
        f"/api/parts/{part.part_number}/shares",
        json={
            "rev": part.revision,
            "expires_in_days": 30,
            "tier": "preview",
            "allow_docpacks": True,
        },
    )
    created = resp.get_json()
    public_client = app.test_client()
    base = f"/api/share/part/{created['share_id']}/{created['share_token']}"

    options = public_client.get(
        f"{base}/docpacks/options?pn={part.part_number}&rev={part.revision}&depth=top"
    )
    assert options.status_code == 200
    offered = options.get_json()["file_types"]
    assert "step" not in offered
    assert "dxf" not in offered
    assert "png" in offered

    named = public_client.post(
        f"{base}/docpacks/build",
        json={
            "pn": part.part_number,
            "rev": part.revision,
            "depth": "top",
            "file_types": ["step"],
            "want_selected_files": True,
        },
    )
    assert named.status_code == 400
    assert named.get_json()["error"] == "invalid_options"

    implied = public_client.post(
        f"{base}/docpacks/build",
        json={
            "pn": part.part_number,
            "rev": part.revision,
            "depth": "top",
            "fabrication_pack": True,
        },
    )
    assert implied.status_code in (400, 404)


def test_datasheets_can_be_shared_without_the_other_uploads(client, app, tmp_path):
    """A datasheet is the manufacturer's published document, not our design data."""

    from app.models.extra_file import PartExtraFile

    app.config["EXTRA_FILES_ROOT"] = str(tmp_path)
    _admin(client, "datasheets@example.com")
    part, _files = _grant_fixture(app, tmp_path, "PN-DATASHEET")
    upload = tmp_path / "extra" / "costing.xlsx"
    upload.parent.mkdir(parents=True, exist_ok=True)
    upload.write_bytes(b"costing")
    PartExtraFile(
        part_number=part.part_number,
        revision=part.revision,
        original_name="costing.xlsx",
        rel_path="extra/costing.xlsx",
        source="upload",
    ).save()

    resp = client.post(
        f"/api/parts/{part.part_number}/shares",
        json={
            "rev": part.revision,
            "expires_in_days": 30,
            "tier": "preview",
            "allow_datasheets": True,
        },
    )
    created = resp.get_json()
    public_client = app.test_client()
    base = f"/api/share/part/{created['share_id']}/{created['share_token']}"

    detail = public_client.get(
        f"{base}/part_detail?pn={part.part_number}&rev={part.revision}"
    ).get_json()
    assert detail["files"]["datasheet"], "the datasheet grant must expose the datasheet"
    assert detail["part"]["field_values"]["datasheet"]

    overview = public_client.get(
        f"{base}/files_overview?pn={part.part_number}&rev={part.revision}"
    ).get_json()
    listed = [row["name"] for row in overview["current_revision"]["files"]]
    assert "PN-DATASHEET.datasheet" in listed
    assert not any(name == "costing.xlsx" for name in listed), (
        "an associated upload needs the All files grant, not the datasheet one"
    )


def test_scope_projections_carry_every_field_the_guard_reads(app, tmp_path):
    """The exact defect behind the blank shared images, pinned.

    allows_managed_file() reads ext_group. A projection that omits it leaves
    the attribute None, the guard denies a file that IS in scope, and the share
    renders with no picture and nothing in any log to say why.
    """
    from app.services.part_shares import (
        ASSOCIATED_FILE_SCOPE_FIELDS,
        MANAGED_FILE_SCOPE_FIELDS,
        PublicPartShareScope,
    )

    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILE_SOURCES"] = [{"local_root": str(tmp_path)}]
    Part(part_number="PN-PROJ", revision="A", description="proj").save()
    rel = "png/PN-PROJ.png"
    abs_path = tmp_path / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(b"png")
    PartFile(
        part_number="PN-PROJ",
        revision="A",
        ext_group="png",
        ext="png",
        is_dwg=False,
        rel_path=rel,
        path=str(abs_path),
    ).save()

    scope = PublicPartShareScope(
        share=None,
        root=("PN-PROJ", "A"),
        allowed_parts=frozenset({("pn-proj", "a")}),
        managed_file_groups=frozenset({"png"}),
    )
    projected = (
        PartFile.objects(part_number="PN-PROJ")
        .only(*MANAGED_FILE_SCOPE_FIELDS)
        .first()
    )
    assert scope.allows_managed_file(projected) is True

    starved = PartFile.objects(part_number="PN-PROJ").only("id", "rel_path").first()
    assert scope.allows_managed_file(starved) is False

    assert "ext_group" in MANAGED_FILE_SCOPE_FIELDS
    assert "is_dwg" in MANAGED_FILE_SCOPE_FIELDS
    assert "original_name" in ASSOCIATED_FILE_SCOPE_FIELDS
