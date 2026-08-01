import io
import json
import os
import zipfile

from app.models.auth import Role
from app.models.part import Part
from app.models.extra_file import PartExtraFile
from app.models.artifact import PartFile
from app.services.standard_roles import STANDARD_ROLES


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _make_bom_zip(
    pn: str,
    rev: str,
    extra_entries: dict[str, bytes],
    *,
    bom_with_utf8_bom: bool = False,
    flat_overrides: dict | None = None,
) -> bytes:
    flat = {"partnumber": pn, "revision": rev, "description": "Test part"}
    if flat_overrides:
        flat.update(flat_overrides)
    flat_txt = "\n".join([repr(flat)])
    tree_txt = "\n".join(
        [
            "ITEM NO.\tPART NUMBER\tRevision\tQTY.",
            f"1\t{pn}\t{rev}\t1",
        ]
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if bom_with_utf8_bom:
            flat_bytes = b"\xef\xbb\xbf" + flat_txt.encode("utf-8")
            zf.writestr("TEST_FLATBOM.txt", flat_bytes)
        else:
            zf.writestr("TEST_FLATBOM.txt", flat_txt)
        zf.writestr("TEST_TREEBOM.txt", tree_txt)
        for name, data in extra_entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_upload_pack_accepts_flatbom_with_bom(client, app, user, tmp_path):
    role = Role(name="importer_bom", permissions=[
            "imports.execute_low_risk",
            "imports.preview",
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "bom.update",
            "comments.write",
            "files.add",
            "files.replace",
            "markups.write",
            "numbering.allocate",
            "parts.create",
            "parts.revise",
            "parts.update",
        ]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        app.config["EXTRA_FILES_ALLOWED"] = True

    pn = "PN-BOM"
    rev = "A"
    zip_bytes = _make_bom_zip(pn, rev, {}, bom_with_utf8_bom=True)

    resp = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(zip_bytes), "pack.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200

    part = Part.objects(part_number=pn, revision=rev).first()
    assert part is not None


def test_upload_pack_imports_extra_with_rev(client, app, user, tmp_path):
    role = Role(
        name="importer",
        permissions=[
            "imports.execute_low_risk",
            "imports.preview",
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "bom.update",
            "comments.write",
            "files.add",
            "files.replace",
            "markups.write",
            "numbering.allocate",
            "parts.create",
            "parts.revise",
            "parts.update",
            "parts.read_unreleased",
        ],
    ).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        app.config["EXTRA_FILES_ALLOWED"] = True

    pn = "PN-1"
    rev = "A"
    entries = {
        f"deliverables/pdf/{pn}_REV_{rev}.pdf": b"pdf",
        f"extra/{pn}/{rev}/scan.e57": b"pointcloud",
    }
    zip_bytes = _make_bom_zip(pn, rev, entries)

    resp = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(zip_bytes), "pack.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200

    ef = PartExtraFile.objects(part_number=pn, revision=rev).first()
    assert ef is not None
    abs_path = os.path.join(tmp_path, ef.rel_path.replace("/", os.sep))
    assert os.path.isfile(abs_path)

    list_resp = client.get(f"/api/parts/{pn}/{rev}/extra")
    assert list_resp.status_code == 200
    rows = list_resp.get_json()
    assert len(rows) == 1


def test_upload_pack_rev_empty_token(client, app, user, tmp_path):
    role = Role(name="importer2", permissions=[
            "imports.execute_low_risk",
            "imports.preview",
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "bom.update",
            "comments.write",
            "files.add",
            "files.replace",
            "markups.write",
            "numbering.allocate",
            "parts.create",
            "parts.revise",
            "parts.update",
        ]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        app.config["EXTRA_FILES_ALLOWED"] = True

    pn = "PN-2"
    rev = ""
    entries = {
        f"extra/{pn}/__no_rev__/note.txt": b"hello",
    }
    zip_bytes = _make_bom_zip(pn, rev, entries)

    resp = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(zip_bytes), "pack.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200

    ef = PartExtraFile.objects(part_number=pn, revision="").first()
    assert ef is not None
    assert "__no_rev__" in (ef.rel_path or "")


def test_upload_pack_legacy_extra_uses_bom_rev(client, app, user, tmp_path):
    role = Role(name="importer3", permissions=[
            "imports.execute_low_risk",
            "imports.preview",
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "bom.update",
            "comments.write",
            "files.add",
            "files.replace",
            "markups.write",
            "numbering.allocate",
            "parts.create",
            "parts.revise",
            "parts.update",
        ]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        app.config["EXTRA_FILES_ALLOWED"] = True

    pn = "PN-3"
    rev = "B"
    entries = {
        f"extra/{pn}/legacy.csv": b"legacy",
    }
    zip_bytes = _make_bom_zip(pn, rev, entries)

    resp = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(zip_bytes), "pack.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200

    ef = PartExtraFile.objects(part_number=pn, revision=rev).first()
    assert ef is not None


def test_upload_pack_extra_label_manifest(client, app, user, tmp_path):
    role = Role(name="importer_label", permissions=[
            "imports.execute_low_risk",
            "imports.preview",
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "bom.update",
            "comments.write",
            "files.add",
            "files.replace",
            "markups.write",
            "numbering.allocate",
            "parts.create",
            "parts.revise",
            "parts.update",
        ]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        app.config["EXTRA_FILES_ALLOWED"] = True

    pn = "PN-LABEL"
    rev = "C"
    extra_name = "report.pdf"
    manifest = {
        "version": 1,
        "files": [
            {"pn": pn, "rev": rev, "name": extra_name, "label": "Inspection report", "ext": "pdf"},
        ],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("TEST_FLATBOM.txt", repr({"partnumber": pn, "revision": rev}))
        zf.writestr("TEST_TREEBOM.txt", f"ITEM NO.\tPART NUMBER\tRevision\tQTY.\n1\t{pn}\t{rev}\t1")
        zf.writestr(f"extra/{pn}/{rev}/{extra_name}", b"data")
        zf.writestr("extra/_manifest.json", json.dumps(manifest))

    resp = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(buf.getvalue()), "pack.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200

    ef = PartExtraFile.objects(part_number=pn, revision=rev).first()
    assert ef is not None
    assert ef.label == "Inspection report"


def test_upload_pack_report_includes_existing_part_file_changes(client, app, user, tmp_path):
    role = Role(name="importer_report", permissions=[
            "imports.execute_low_risk",
            "imports.preview",
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "bom.update",
            "comments.write",
            "files.add",
            "files.replace",
            "markups.write",
            "numbering.allocate",
            "parts.create",
            "parts.revise",
            "parts.update",
        ]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        app.config["EXTRA_FILES_ALLOWED"] = True

    pn = "PN-REPORT"
    rev = "A"
    Part(part_number=pn, revision=rev, description="Existing part").save()
    entries = {
        f"deliverables/pdf/{pn}_REV_{rev}.pdf": b"pdf",
        f"extra/{pn}/{rev}/inspection.txt": b"report",
    }
    zip_bytes = _make_bom_zip(pn, rev, entries)

    resp = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(zip_bytes), "pack.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    data = resp.get_json() or {}
    plan = data.get("plan") or {}

    entry = next(
        (
            item
            for item in plan.get("parts") or []
            if item.get("part_number") == pn and item.get("revision") == rev
        ),
        None,
    )
    assert entry is not None
    file_rows = entry.get("files") or []
    kinds = {item.get("kind") for item in file_rows}
    assert kinds == {"managed", "associated"}
    assert all(item.get("action") == "add" for item in file_rows)


def test_upload_pack_scans_attr_named_datasheet_when_other_deliverables_are_parsed(client, app, user, tmp_path):
    role = Role(name="importer_datasheet", permissions=[
            "imports.execute_low_risk",
            "imports.preview",
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "bom.update",
            "comments.write",
            "files.add",
            "files.replace",
            "markups.write",
            "numbering.allocate",
            "parts.create",
            "parts.revise",
            "parts.update",
        ]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        app.config["EXTRA_FILES_ALLOWED"] = True

    pn = "PN-DS-PACK"
    rev = "A"
    entries = {
        f"deliverables/pdf/{pn}_REV_{rev}.pdf": b"pdf",
        "deliverables/datasheet/vendor-file.pdf": b"datasheet",
    }
    zip_bytes = _make_bom_zip(
        pn,
        rev,
        entries,
        flat_overrides={"datasheet": "vendor-file.pdf"},
    )

    resp = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(zip_bytes), "pack.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200

    datasheet = PartFile.objects(
        part_number=pn,
        revision=rev,
        ext_group="datasheet",
        rel_path="datasheet/vendor-file.pdf",
    ).first()
    assert datasheet is not None


def test_direct_extra_upload_empty_rev(client, app, user, tmp_path):
    role = Role(
        name="editor",
        permissions=[
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "bom.update",
            "comments.write",
            "files.add",
            "files.replace",
            "markups.write",
            "numbering.allocate",
            "parts.create",
            "parts.revise",
            "parts.update",
            "parts.read_unreleased",
        ],
    ).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        app.config["EXTRA_FILES_ALLOWED"] = True

    pn = "PN-4"
    rev = "__no_rev__"
    Part(part_number=pn, revision="", description="Blank revision").save()
    resp = client.post(
        f"/api/parts/{pn}/{rev}/extra",
        data={"file": (io.BytesIO(b"data"), "sample.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    ef = PartExtraFile.objects(part_number=pn, revision="").first()
    assert ef is not None


def test_extra_delete_requires_permission(client, app, user, tmp_path):
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

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        app.config["EXTRA_FILES_ALLOWED"] = True

    pn = "PN-5"
    Part(
        part_number=pn,
        revision="",
        description="Released blank revision",
        attrs={"approvedby": "QA"},
    ).save()
    ef = PartExtraFile(
        part_number=pn,
        revision="",
        original_name="sample.txt",
        rel_path=f"extra/{pn}/__no_rev__/sample.txt",
        size=1,
        mime="text/plain",
        sha256="",
    )
    ef.save()

    resp = client.delete(f"/api/parts/{pn}/__no_rev__/extra/{ef.id}")
    assert resp.status_code == 404


def test_upload_pack_zip_slip_rejected(client, app, user, tmp_path):
    role = Role(name="importer4", permissions=[
            "imports.execute_low_risk",
            "imports.preview",
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "bom.update",
            "comments.write",
            "files.add",
            "files.replace",
            "markups.write",
            "numbering.allocate",
            "parts.create",
            "parts.revise",
            "parts.update",
        ]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        app.config["EXTRA_FILES_ALLOWED"] = True

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("../evil.txt", b"bad")
    resp = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(buf.getvalue()), "pack.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_import_capabilities_endpoint_is_lightweight_and_exact(client, app, user):
    role = Role(
        name="capabilities-preview",
        permissions=["imports.preview", "imports.execute_low_risk"],
    ).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    resp = client.get("/api/import/capabilities")
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    assert payload == {
        "imports": {
            "imports.execute_approved": False,
            "imports.execute_low_risk": True,
            "imports.override_approved": False,
            "imports.preview": True,
        }
    }


def test_import_execution_permission_does_not_grant_resource_writes(
    client,
    app,
    user,
    tmp_path,
):
    """imports.* alone must not create parts; parts/bom/files writes are separate."""
    role = Role(
        name="imports-only",
        permissions=[
            "imports.preview",
            "imports.execute_low_risk",
            "imports.execute_approved",
            "imports.override_approved",
        ],
    ).save()
    user.roles = [role]
    user.save()
    _login(client, user)
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    zip_bytes = _make_bom_zip("IMPORTS-ONLY", "A", {})

    resp = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(zip_bytes), "pack.zip")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 403
    missing = (resp.get_json() or {}).get("missing_permissions") or []
    assert "parts.create" in missing
    assert Part.objects(part_number="IMPORTS-ONLY", revision="A").first() is None


def test_resource_writes_do_not_grant_import_execution(client, app, user, tmp_path):
    role = Role(
        name="writes-only",
        permissions=[
            "imports.preview",
            "parts.create",
            "parts.update",
            "bom.update",
            "files.add",
            "files.replace",
        ],
    ).save()
    user.roles = [role]
    user.save()
    _login(client, user)
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    zip_bytes = _make_bom_zip("WRITES-ONLY", "A", {})

    resp = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(zip_bytes), "pack.zip")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 403
    missing = (resp.get_json() or {}).get("missing_permissions") or []
    assert "imports.execute_low_risk" in missing
    assert Part.objects(part_number="WRITES-ONLY", revision="A").first() is None


def test_upload_pack_preview_and_execution_permissions_are_separate(
    client,
    app,
    user,
    tmp_path,
):
    role = Role(name="preview-only", permissions=["imports.preview"]).save()
    user.roles = [role]
    user.save()
    _login(client, user)
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    zip_bytes = _make_bom_zip("PREVIEW-ONLY", "A", {})

    preview = client.post(
        "/api/upload/pack",
        data={
            "file": (io.BytesIO(zip_bytes), "preview.zip"),
            "dry_run": "true",
        },
        content_type="multipart/form-data",
    )
    execute = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(zip_bytes), "execute.zip")},
        content_type="multipart/form-data",
    )

    assert preview.status_code == 200
    assert preview.get_json()["dry_run"] is True
    assert execute.status_code == 403
    assert Part.objects(part_number="PREVIEW-ONLY", revision="A").first() is None


def test_upload_pack_low_risk_user_cannot_override_released_part(
    client,
    app,
    user,
    tmp_path,
):
    role = Role(
        name="low-risk-only",
        permissions=["imports.preview", "imports.execute_low_risk"],
    ).save()
    user.roles = [role]
    user.save()
    _login(client, user)
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    part = Part(
        part_number="APPROVED-IMPORT",
        revision="A",
        description="Released",
        attrs={"approvedby": "QA"},
    ).save()
    zip_bytes = _make_bom_zip(
        part.part_number,
        part.revision,
        {f"deliverables/pdf/{part.part_number}_REV_A.pdf": b"new"},
        flat_overrides={"description": "Overwritten"},
    )

    always = client.post(
        "/api/upload/pack",
        data={
            "file": (io.BytesIO(zip_bytes), "always.zip"),
            "data_mode": "replace_all",
            "bom_mode": "replace_all",
            "file_mode": "replace_all",
            "approval_mode": "replace_all",
        },
        content_type="multipart/form-data",
    )
    default = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(zip_bytes), "default.zip")},
        content_type="multipart/form-data",
    )

    assert always.status_code == 403
    assert default.status_code == 403
    part.reload()
    assert part.description == "Released"
    assert not (tmp_path / "pdf" / f"{part.part_number}_REV_A.pdf").exists()


def test_upload_pack_override_authority_can_intentionally_update_released_part(
    client,
    app,
    user,
    tmp_path,
):
    role = Role(
        name="engineering_manager",
        permissions=list(STANDARD_ROLES["engineering_manager"].permissions),
    ).save()
    user.roles = [role]
    user.save()
    _login(client, user)
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    part = Part(
        part_number="APPROVED-OVERRIDE",
        revision="A",
        description="Released",
        attrs={"approvedby": "QA"},
    ).save()
    assert client.get("/ui/upload-pack").status_code == 200
    zip_bytes = _make_bom_zip(
        part.part_number,
        part.revision,
        {},
        flat_overrides={"description": "Authorized replacement"},
    )

    response = client.post(
        "/api/upload/pack",
        data={
            "file": (io.BytesIO(zip_bytes), "approved-override.zip"),
            "data_mode": "replace_all",
            "bom_mode": "replace_all",
            "file_mode": "replace_all",
            "approval_mode": "replace_all",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    part.reload()
    assert part.description == "Authorized replacement"


def test_upload_pack_preserve_mode_does_not_replace_existing_files(
    client,
    app,
    user,
    tmp_path,
):
    role = Role(
        name="preserve-importer",
        permissions=["imports.preview", "imports.execute_low_risk"],
    ).save()
    user.roles = [role]
    user.save()
    _login(client, user)
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    app.config["EXTRA_FILES_ALLOWED"] = True
    pn = "PRESERVE-FILE"
    Part(part_number=pn, revision="A", description="Existing").save()
    pdf_path = tmp_path / "pdf" / f"{pn}_REV_A.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"original")
    PartFile(
        part_number=pn,
        revision="A",
        ext_group="pdf",
        ext="pdf",
        rel_path=f"pdf/{pn}_REV_A.pdf",
        path=str(pdf_path),
    ).save()
    associated_path = tmp_path / "extra" / pn / "A" / "inspection.txt"
    associated_path.parent.mkdir(parents=True)
    associated_path.write_bytes(b"original associated")
    PartExtraFile(
        part_number=pn,
        revision="A",
        original_name="inspection.txt",
        rel_path=f"extra/{pn}/A/inspection.txt",
        size=float(associated_path.stat().st_size),
        mime="text/plain",
        sha256="original-hash",
    ).save()
    zip_bytes = _make_bom_zip(
        pn,
        "A",
        {
            f"deliverables/pdf/{pn}_REV_A.pdf": b"replacement",
            f"extra/{pn}/A/inspection.txt": b"replacement associated",
        },
        flat_overrides={"description": "Incoming"},
    )

    response = client.post(
        "/api/upload/pack",
        data={
            "file": (io.BytesIO(zip_bytes), "preserve.zip"),
            "data_mode": "fill_blanks",
            "bom_mode": "fill_if_empty",
            "file_mode": "add_missing",
            "approval_mode": "preserve",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert pdf_path.read_bytes() == b"original"
    assert associated_path.read_bytes() == b"original associated"
    assert PartFile.objects(part_number=pn, revision="A").count() == 1
    assert PartExtraFile.objects(part_number=pn, revision="A").count() == 1
    part = Part.objects(part_number=pn, revision="A").first()
    assert part.description == "Existing"


def test_files_overview_separates_current_and_other_revisions(client, app, user, tmp_path):
    role = Role(
        name="files_overview",
        permissions=[
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "bom.update",
            "comments.write",
            "files.add",
            "files.replace",
            "markups.write",
            "numbering.allocate",
            "parts.create",
            "parts.revise",
            "parts.update",
            "parts.read_unreleased",
        ],
    ).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        app.config["EXTRA_FILES_ALLOWED"] = True

    pn = "PN-VIS"
    current_rev = "A"
    other_rev = "B"
    Part(part_number=pn, revision=current_rev, description="Current rev").save()
    Part(part_number=pn, revision=other_rev, description="Other rev").save()
    PartFile(
        part_number=pn,
        revision=current_rev,
        ext_group="pdf",
        ext="pdf",
        rel_path=f"pdf/{pn}_REV_{current_rev}.pdf",
        path=str(tmp_path / "pdf" / f"{pn}_REV_{current_rev}.pdf"),
        source="scan",
    ).save()
    PartFile(
        part_number=pn,
        revision=other_rev,
        ext_group="step",
        ext="step",
        rel_path=f"step/{pn}_REV_{other_rev}.step",
        path=str(tmp_path / "step" / f"{pn}_REV_{other_rev}.step"),
        source="scan",
    ).save()
    PartExtraFile(
        part_number=pn,
        revision=current_rev,
        original_name="note.txt",
        rel_path=f"extra/{pn}/{current_rev}/note.txt",
        size=12,
        mime="text/plain",
        sha256="",
        uploaded_by="user@example.com",
    ).save()
    PartExtraFile(
        part_number=pn,
        revision=other_rev,
        original_name="legacy.csv",
        rel_path=f"extra/{pn}/{other_rev}/legacy.csv",
        size=24,
        mime="text/csv",
        sha256="",
        uploaded_by="user@example.com",
    ).save()

    resp = client.get(f"/api/parts/{pn}/files_overview?rev={current_rev}")
    assert resp.status_code == 200
    data = resp.get_json()

    current_section = data["current_revision"]
    assert current_section["revision"] == current_rev
    assert current_section["counts"]["part_files"] == 1
    assert current_section["counts"]["part_extra_files"] == 1
    current_names = {row["name"] for row in current_section["files"]}
    assert f"{pn}_REV_{current_rev}.pdf" in current_names
    assert "note.txt" in current_names

    assert len(data["other_revisions"]) == 1
    other_section = data["other_revisions"][0]
    assert other_section["revision"] == other_rev
    assert {row["kind"] for row in other_section["files"]} == {"scanned", "extra"}
    assert all("collection" not in row for row in other_section["files"])
    assert all("db_id" not in row for row in other_section["files"])
    assert all("rel_path" not in row for row in other_section["files"])
