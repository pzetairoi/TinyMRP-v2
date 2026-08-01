import io
import zipfile

from app.models.auth import Role
from app.models.part import Part


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _make_zip(flat_txt: str, tree_txt: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("TEST_FLATBOM.txt", flat_txt)
        zf.writestr("TEST_TREEBOM.txt", tree_txt)
    return buf.getvalue()


def test_upload_pack_returns_import_report_on_parse_errors(client, app, user, tmp_path):
    role = Role(name="importer_partial", permissions=[
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

    pn = "UP-ERR"
    rev = "A"
    flat_txt = "\n".join(
        [
            repr({"partnumber": pn, "revision": rev, "description": "Ok"}),
            "{'partnumber': 'BROKEN'",  # malformed -> should be reported, but request still succeeds
        ]
    )
    tree_txt = "\n".join(
        [
            "ITEM NO.\tPART NUMBER\tRevision\tQTY.",
            f"1\t{pn}\t{rev}\t1",
        ]
    )
    zip_bytes = _make_zip(flat_txt, tree_txt)

    resp = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(zip_bytes), "pack.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    data = resp.get_json() or {}
    assert (data.get("diagnostics") or {}).get("flat_lines_failed_parse") == 1
    assert len(data.get("errors") or []) >= 1

    part = Part.objects(part_number=pn, revision=rev).first()
    assert part is not None

