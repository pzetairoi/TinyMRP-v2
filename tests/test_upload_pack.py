import io
import json
import os
import zipfile

from app.models.auth import Role
from app.models.part import Part
from app.models.extra_file import PartExtraFile


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
) -> bytes:
    flat = {"partnumber": pn, "revision": rev, "description": "Test part"}
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
    role = Role(name="importer_bom", permissions=["import.bom", "items.view", "items.edit"]).save()
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
    role = Role(name="importer", permissions=["import.bom", "items.view", "items.edit"]).save()
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
    role = Role(name="importer2", permissions=["import.bom", "items.view", "items.edit"]).save()
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
    role = Role(name="importer3", permissions=["import.bom", "items.view", "items.edit"]).save()
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
    role = Role(name="importer_label", permissions=["import.bom", "items.view", "items.edit"]).save()
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


def test_direct_extra_upload_empty_rev(client, app, user, tmp_path):
    role = Role(name="editor", permissions=["items.view", "items.edit"]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        app.config["EXTRA_FILES_ALLOWED"] = True

    pn = "PN-4"
    rev = "__no_rev__"
    resp = client.post(
        f"/api/parts/{pn}/{rev}/extra",
        data={"file": (io.BytesIO(b"data"), "sample.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    ef = PartExtraFile.objects(part_number=pn, revision="").first()
    assert ef is not None


def test_extra_delete_requires_permission(client, app, user, tmp_path):
    role = Role(name="viewer", permissions=["items.view"]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        app.config["EXTRA_FILES_ALLOWED"] = True

    pn = "PN-5"
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
    assert resp.status_code == 403


def test_upload_pack_zip_slip_rejected(client, app, user, tmp_path):
    role = Role(name="importer4", permissions=["import.bom", "items.view", "items.edit"]).save()
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
