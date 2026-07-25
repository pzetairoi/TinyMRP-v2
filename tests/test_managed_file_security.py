import io
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.artifact import PartFile
from app.models.auth import Role, User
from app.models.customer import Customer
from app.models.extra_file import PartExtraFile
from app.models.job import Job, JobBOMLine
from app.models.order import Order, OrderLine
from app.models.part import Part
from app.models.supplier import Supplier
from app.services.file_security import FileSecurityError, resolve_managed_path
from app.services.files_access import file_token_for
from app.services.standard_roles import STANDARD_ROLES


def _role(name, permissions):
    return Role(name=name, permissions=list(permissions)).save()


def _standard_role(name):
    definition = STANDARD_ROLES[name]
    return _role(name, definition.permissions)


def _user(email, *roles):
    return User(
        email=email,
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=list(roles),
    ).save()


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = user.get_id()
        session["_fresh"] = True


def _part(pn, rev="A", *, released=False):
    return Part(
        part_number=pn,
        revision=rev,
        attrs={"approvedby": "QA"} if released else {},
    ).save()


def _managed(root, pn, rev, group="pdf", content=b"managed"):
    path = root / group / f"{pn}_REV_{rev}.{group}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return PartFile(
        part_number=pn,
        revision=rev,
        ext_group=group,
        ext=group,
        rel_path=f"{group}/{path.name}",
        path=str(path),
        source="primary",
    ).save()


def _token(app, file_record):
    with app.app_context():
        return file_token_for(file_record)


def test_managed_download_requires_file_permission_and_exact_release_scope(
    client, app, tmp_path
):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    released = _part("FILE-R", released=True)
    draft = _part("FILE-D")
    released_file = _managed(tmp_path, released.part_number, released.revision)
    draft_file = _managed(tmp_path, draft.part_number, draft.revision)

    released_reader = _user(
        "released@files.test",
        _role("released_reader", ["parts.read", "files.read"]),
    )
    _login(client, released_reader)
    assert client.get(f"/files/view/{_token(app, released_file)}").status_code == 200
    assert client.get(f"/files/view/{_token(app, draft_file)}").status_code == 404

    draft_reader = _user(
        "draft@files.test",
        _role(
            "draft_reader",
            ["parts.read", "parts.read_unreleased", "files.read"],
        ),
    )
    _login(client, draft_reader)
    assert client.get(f"/files/view/{_token(app, draft_file)}").status_code == 200

    no_files = _user(
        "parts-only@files.test",
        _role("parts_only", ["parts.read", "parts.read_unreleased"]),
    )
    _login(client, no_files)
    assert client.get(f"/files/view/{_token(app, draft_file)}").status_code == 404


def test_file_token_stays_bound_to_exact_blank_or_named_revision(client, app, tmp_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    part = _part("TOKEN-EXACT", "", released=True)
    file_record = _managed(tmp_path, part.part_number, "", content=b"blank")
    reader = _user(
        "token@files.test",
        _role("token_reader", ["parts.read", "files.read"]),
    )
    token = _token(app, file_record)
    file_record.revision = "A"
    file_record.save()
    _login(client, reader)
    assert client.get(f"/files/view/{token}").status_code == 404


def test_security_and_system_administrators_alone_cannot_download(
    client, app, tmp_path
):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    part = _part("ADMIN-NO-FILE", released=True)
    file_record = _managed(tmp_path, part.part_number, part.revision)
    token = _token(app, file_record)
    for role_name in ("security_administrator", "system_administrator"):
        user = _user(f"{role_name}@files.test", _standard_role(role_name))
        _login(client, user)
        assert client.get(f"/files/view/{token}").status_code == 404


def test_customer_portal_file_list_is_exact_and_hides_internal_cad(
    client, app, tmp_path
):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    allowed = _part("PORTAL-FILE", "A", released=True)
    _part("PORTAL-FILE", "B", released=True)
    _managed(tmp_path, allowed.part_number, "A", "pdf")
    _managed(tmp_path, allowed.part_number, "A", "step")
    _managed(tmp_path, allowed.part_number, "B", "pdf")
    portal = _user("portal@files.test", _standard_role("customer_portal"))
    customer = Customer(name="File Customer", users=[portal]).save()
    Job(
        job_number="FILE-JOB",
        customer=customer,
        bom=[JobBOMLine(pn=allowed.part_number, rev="A", qty=1)],
    ).save()
    _login(client, portal)

    response = client.get("/api/parts/PORTAL-FILE/files_overview?rev=A")
    assert response.status_code == 200
    rows = response.get_json()["current_revision"]["files"]
    assert {row["ext_group"] for row in rows} == {"pdf"}
    assert client.get("/api/parts/PORTAL-FILE/files_overview?rev=B").status_code == 404


def test_supplier_and_production_file_access_follow_exact_relationships(
    client, app, tmp_path
):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    allowed = _part("SUP-FILE", "A", released=True)
    denied = _part("SUP-FILE", "B", released=True)
    allowed_file = _managed(tmp_path, allowed.part_number, "A", "step")
    denied_file = _managed(tmp_path, denied.part_number, "B", "step")

    supplier_user = _user("supplier@files.test", _standard_role("supplier_portal"))
    supplier = Supplier(name="File Supplier", users=[supplier_user]).save()
    Order(
        order_number="FILE-PO",
        kind="purchase",
        supplier=supplier,
        lines=[OrderLine(pn=allowed.part_number, rev="A", qty=1)],
    ).save()
    _login(client, supplier_user)
    assert client.get(f"/files/view/{_token(app, allowed_file)}").status_code == 200
    assert client.get(f"/files/view/{_token(app, denied_file)}").status_code == 404

    operator = _user("operator@files.test", _standard_role("production_operator"))
    Job(
        job_number="FILE-PRODUCTION",
        participants=[operator],
        bom=[JobBOMLine(pn=allowed.part_number, rev="A", qty=1)],
    ).save()
    _login(client, operator)
    assert client.get(f"/files/view/{_token(app, allowed_file)}").status_code == 200
    assert client.get(f"/files/view/{_token(app, denied_file)}").status_code == 404


@pytest.mark.parametrize(
    "rel_path",
    (
        "../escape.pdf",
        "pdf/../../escape.pdf",
        "/absolute/escape.pdf",
        r"..\escape.pdf",
    ),
)
def test_managed_path_rejects_traversal_and_absolute_forms(app, tmp_path, rel_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path / "root")
    record = SimpleNamespace(
        path="",
        rel_path=rel_path,
        source="primary",
        thumb_rel_path="",
    )
    with pytest.raises(FileSecurityError):
        with app.app_context():
            resolve_managed_path(record, must_exist=False)


def test_managed_path_rejects_sibling_prefix_and_accepts_regular_file(app, tmp_path):
    root = tmp_path / "files"
    sibling = tmp_path / "files-escape"
    sibling.mkdir()
    outside = sibling / "outside.pdf"
    outside.write_bytes(b"outside")
    app.config["FILE_ROOT_LOCAL"] = str(root)
    with pytest.raises(FileSecurityError):
        with app.app_context():
            resolve_managed_path(
                SimpleNamespace(path=str(outside), rel_path="", source=""),
            )

    inside = root / "pdf" / "inside.pdf"
    inside.parent.mkdir(parents=True)
    inside.write_bytes(b"inside")
    with app.app_context():
        assert resolve_managed_path(
            SimpleNamespace(
                path=str(inside),
                rel_path="pdf/inside.pdf",
                source="primary",
            )
        ) == inside.resolve()


def test_managed_path_rejects_symlink_escape_where_supported(app, tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.pdf").write_bytes(b"secret")
    link = root / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    app.config["FILE_ROOT_LOCAL"] = str(root)
    with pytest.raises(FileSecurityError):
        with app.app_context():
            resolve_managed_path(
                SimpleNamespace(
                    path="",
                    rel_path="link/secret.pdf",
                    source="primary",
                )
            )


def test_associated_upload_replacement_and_validation_are_consistent(
    client, app, tmp_path
):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    app.config["EXTRA_FILES_ALLOWED"] = True
    part = _part("EXTRA-MUT", "")
    engineer = _user(
        "engineer@files.test",
        _standard_role("engineering_data_steward"),
    )
    _login(client, engineer)
    url = f"/api/parts/{part.part_number}/__no_rev__/extra"

    added = client.post(
        url,
        data={"file": (io.BytesIO(b"old"), "../../note.txt")},
        content_type="multipart/form-data",
    )
    assert added.status_code == 200
    record = PartExtraFile.objects.get(part_number=part.part_number, revision="")
    physical = tmp_path / record.rel_path
    assert physical.read_bytes() == b"old"
    assert not (tmp_path.parent / "note.txt").exists()

    replaced = client.post(
        url,
        data={"file": (io.BytesIO(b"new"), "note.txt")},
        content_type="multipart/form-data",
    )
    assert replaced.status_code == 200
    assert physical.read_bytes() == b"new"

    app.config["UPLOAD_PACK_MAX_FILE_MB"] = 1
    too_large = client.post(
        url,
        data={"file": (io.BytesIO(b"x" * (1024 * 1024 + 1)), "note.txt")},
        content_type="multipart/form-data",
    )
    assert too_large.status_code == 413
    assert physical.read_bytes() == b"new"

    rejected = client.post(
        url,
        data={"file": (io.BytesIO(b"danger"), "payload.exe")},
        content_type="multipart/form-data",
    )
    assert rejected.status_code == 400
    assert physical.read_bytes() == b"new"
    assert PartExtraFile.objects(part_number=part.part_number).count() == 1


def test_associated_upload_requires_add_replace_scope_and_mutable_revision(
    client, app, tmp_path
):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    draft = _part("EXTRA-DENY", "A")
    released = _part("EXTRA-REL", "A", released=True)
    viewer = _user(
        "viewer@files.test",
        _standard_role("internal_viewer"),
    )
    _login(client, viewer)
    assert client.post(
        f"/api/parts/{draft.part_number}/A/extra",
        data={"file": (io.BytesIO(b"x"), "x.txt")},
        content_type="multipart/form-data",
    ).status_code == 404

    engineer = _user(
        "released-engineer@files.test",
        _standard_role("engineering_data_steward"),
    )
    _login(client, engineer)
    assert client.post(
        f"/api/parts/{released.part_number}/A/extra",
        data={"file": (io.BytesIO(b"x"), "x.txt")},
        content_type="multipart/form-data",
    ).status_code == 404
    assert PartExtraFile.objects.count() == 0


def test_associated_purge_requires_explicit_files_purge(client, app, tmp_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    part = _part("EXTRA-PURGE", "A")
    rel = "extra/EXTRA-PURGE/A/report.txt"
    physical = tmp_path / rel
    physical.parent.mkdir(parents=True)
    physical.write_bytes(b"report")
    record = PartExtraFile(
        part_number=part.part_number,
        revision=part.revision,
        original_name="report.txt",
        rel_path=rel,
    ).save()
    engineer = _user("no-purge@files.test", _standard_role("engineering_data_steward"))
    _login(client, engineer)
    endpoint = f"/api/parts/{part.part_number}/A/extra/{record.id}"
    assert client.delete(endpoint).status_code == 404
    assert physical.exists()
    assert PartExtraFile.objects(id=record.id).first() is not None

    purger = _user(
        "purger@files.test",
        _role(
            "file_purger",
            [
                "parts.read",
                "parts.read_unreleased",
                "files.purge",
            ],
        ),
    )
    _login(client, purger)
    assert client.delete(endpoint).status_code == 200
    assert not physical.exists()
    assert PartExtraFile.objects(id=record.id).first() is None


def test_part_physical_delete_requires_parts_and_files_purge(
    client, app, tmp_path
):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    part = _part("PART-PURGE", "A", released=True)
    file_record = _managed(tmp_path, part.part_number, part.revision)

    parts_only = _user(
        "parts-purge@files.test",
        _role("parts_purge_only", ["parts.purge"]),
    )
    _login(client, parts_only)
    payload = {"pn": part.part_number, "rev": "A", "delete_files": True}
    assert client.post("/api/part_delete", json=payload).status_code == 403
    assert Path(file_record.path).exists()
    assert Part.objects(id=part.id).first() is not None

    files_only = _user(
        "files-purge@files.test",
        _role("files_purge_only", ["files.purge"]),
    )
    _login(client, files_only)
    assert client.post("/api/part_delete", json=payload).status_code == 403
    assert Part.objects(id=part.id).first() is not None

    both = _user(
        "both-purge@files.test",
        _role("both_purge", ["parts.purge", "files.purge"]),
    )
    _login(client, both)
    assert client.post("/api/part_delete", json=payload).status_code == 200
    assert Part.objects(id=part.id).first() is None
    assert not Path(file_record.path).exists()


def test_legacy_admin_physical_delete_depends_on_compatibility_flag(
    client, app, tmp_path
):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    part = _part("LEGACY-PURGE", "A", released=True)
    file_record = _managed(tmp_path, part.part_number, "A")
    legacy = _user("legacy@files.test", _role("admin", []))
    _login(client, legacy)
    payload = {"pn": part.part_number, "rev": "A", "delete_files": True}

    app.config["LEGACY_ADMIN_BYPASS_ENABLED"] = False
    assert client.post("/api/part_delete", json=payload).status_code == 403
    assert Path(file_record.path).exists()
    assert Part.objects(id=part.id).first() is not None

    app.config["LEGACY_ADMIN_BYPASS_ENABLED"] = True
    assert client.post("/api/part_delete", json=payload).status_code == 200
    assert not Path(file_record.path).exists()
    assert Part.objects(id=part.id).first() is None


def test_refresh_preflights_add_and_stale_removal_permissions(
    client, app, tmp_path
):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    part = _part("REFRESH-SEC", "A")
    stale = PartFile(
        part_number=part.part_number,
        revision="A",
        ext_group="pdf",
        ext="pdf",
        rel_path="pdf/missing.pdf",
        path=str(tmp_path / "pdf" / "missing.pdf"),
        source="primary",
    ).save()
    engineer = _user(
        "refresh@files.test",
        _standard_role("engineering_data_steward"),
    )
    _login(client, engineer)
    response = client.post(
        f"/api/parts/{part.part_number}/refresh_files",
        json={"rev": "A"},
    )
    assert response.status_code == 404
    assert PartFile.objects(id=stale.id).first() is not None


def test_revision_clone_does_not_copy_file_metadata_or_share_physical_path(
    client, app, tmp_path
):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    source = _part("REV-FILE", "A", released=True)
    source_file = _managed(tmp_path, source.part_number, source.revision)
    engineer = _user(
        "revise@files.test",
        _standard_role("engineering_data_steward"),
    )
    _login(client, engineer)
    response = client.post(
        f"/api/numbering/parts/{source.part_number}/revise",
        json={"change_note": "File-safe revision"},
    )
    assert response.status_code == 200
    assert Part.objects(part_number=source.part_number, revision="B").first()
    assert PartFile.objects(part_number=source.part_number, revision="B").count() == 0
    assert Path(source_file.path).exists()
