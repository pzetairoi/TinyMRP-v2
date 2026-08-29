import io
import json
import os
import re
import uuid
from datetime import timedelta
from urllib.parse import urlsplit

import openpyxl
from bson import ObjectId

from app.services.permissions import PERMISSION_REGISTRY
from app.models.artifact import PartFile
from app.models.audit import AuditLog
from app.models.auth import Role, User
from app.models.bom import BOMLink
from app.models.extra_file import PartExtraFile
from app.models.part import Part
from app.models.part_share import PartShareLink
from app.services.extra_files import extra_file_token_for
from app.services.files_access import file_token_for
from app.services.part_shares import hash_part_share_token
from app.services.standard_roles import STANDARD_ROLES
from app.services.timezone_utils import utc_now


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = user.get_id()
        session["_fresh"] = True


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


def _admin(email="stage3b2b-admin@example.test"):
    # An administrator holds permissions explicitly. This used to fall back to
    # an empty role named "admin", which worked only because that name bypassed
    # the permission registry entirely.
    role = Role.objects(name="administrator").first() or _role(
        "administrator", sorted(PERMISSION_REGISTRY)
    )
    return _user(email, role)


def _released(pn, rev, **kwargs):
    attrs = dict(kwargs.pop("attrs", {}) or {})
    attrs["approvedby"] = "QA"
    return Part(
        part_number=pn,
        revision=rev,
        attrs=attrs,
        **kwargs,
    ).save()


def _managed_file(root, part, group="pdf", content=b"file"):
    rel = f"{group}/{part.part_number}_REV_{part.revision}.{group}"
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return PartFile(
        part_number=part.part_number,
        revision=part.revision,
        ext_group=group,
        ext=group,
        rel_path=rel,
        path=str(path),
        content_type="application/pdf" if group == "pdf" else "",
    ).save()


def _create_share(client, part, **options):
    # These are scope tests: they ask which PARTS and which FILES a token
    # reaches, not which file types a level grants. Default to the widest
    # level so a denial here still means the scope check denied it.
    payload = {
        "rev": part.revision,
        "expires_in_days": 30,
        "tier": "full",
        **options,
    }
    response = client.post(
        f"/api/parts/{part.part_number}/shares",
        json=payload,
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def _compile_workbook(pn, rev):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "COMPILE"
    sheet.append(["PartNumber", "Revision", "Qty"])
    sheet.append([pn, rev, 1])
    payload = io.BytesIO()
    workbook.save(payload)
    return payload.getvalue()


def test_exports_run_and_unreleased_authority_are_required_for_arena(client):
    root = Part(part_number="EXP-DRAFT", revision="A").save()
    no_export = _user(
        "no-export@example.test",
        _role(
            "no-export",
            ["parts.read", "parts.read_unreleased", "bom.read"],
        ),
    )
    _login(client, no_export)
    denied = client.post(
        f"/api/parts/{root.part_number}/export/arena_bom",
        json={"rev": "A"},
    )
    assert denied.status_code == 403

    released_only = _user(
        "released-export@example.test",
        _role("released-export", ["exports.run", "parts.read", "bom.read"]),
    )
    _login(client, released_only)
    unreleased_denied = client.post(
        f"/api/parts/{root.part_number}/export/arena_bom",
        json={"rev": "A"},
    )
    assert unreleased_denied.status_code == 404

    engineer = _user(
        "engineer-export@example.test",
        _standard_role("engineering"),
    )
    _login(client, engineer)
    allowed = client.post(
        f"/api/parts/{root.part_number}/export/arena_bom",
        json={"rev": "A"},
    )
    assert allowed.status_code == 200


def test_standard_non_export_roles_and_disabled_legacy_admin_are_denied(client, app):
    part = _released("EXP-ROLE", "A")
    for role_name in (
        "auditor",
        "security_administrator",
        "customer",
        "supplier",
    ):
        user = _user(
            f"{role_name}@export-role.example.test",
            _standard_role(role_name),
        )
        _login(client, user)
        response = client.post(
            f"/api/parts/{part.part_number}/export/arena_bom",
            json={"rev": part.revision},
        )
        assert response.status_code == 403, role_name

    for role_name in ("commercial", "internal"):
        user = _user(
            f"{role_name}@export-role.example.test",
            _standard_role(role_name),
        )
        _login(client, user)
        response = client.post(
            f"/api/parts/{part.part_number}/export/arena_bom",
            json={"rev": part.revision},
        )
        assert response.status_code == 200, role_name

    # An administrator can export because the role lists the permission, not
    # because of its name. The old bypass flag is gone and setting it changes
    # nothing.
    administrator = _admin("administrator-export@example.test")
    _login(client, administrator)
    assert client.post(
        f"/api/parts/{part.part_number}/export/arena_bom",
        json={"rev": part.revision},
    ).status_code == 200

    nameless_admin = _user(
        "bare-admin@export-role.example.test", _role("admin", [])
    )
    _login(client, nameless_admin)
    assert client.post(
        f"/api/parts/{part.part_number}/export/arena_bom",
        json={"rev": part.revision},
    ).status_code == 403


def test_arena_export_is_exact_and_scope_failure_rejects_complete_bom(
    client,
    monkeypatch,
):
    admin = _admin()
    root_a = _released("EXP-EXACT", "A", description="Revision A")
    _released("EXP-EXACT", "B", description="Revision B")
    child = _released("EXP-CHILD", "A")
    BOMLink(
        parent_pn=root_a.part_number,
        parent_rev="A",
        child_pn=child.part_number,
        child_rev="A",
        qty=1,
    ).save()
    _login(client, admin)

    response = client.post(
        f"/api/parts/{root_a.part_number}/export/arena_bom",
        json={"rev": "A"},
    )
    assert response.status_code == 200
    assert b"Revision A" in response.data
    assert b"Revision B" not in response.data

    monkeypatch.setattr(
        "app.services.export_security.authorised_part_pairs",
        lambda *_args, **_kwargs: frozenset(),
    )
    denied = client.post(
        f"/api/parts/{root_a.part_number}/export/arena_bom",
        json={"rev": "A"},
    )
    assert denied.status_code == 403
    assert child.part_number.encode() not in denied.data


def test_docpack_preflight_rejects_unsafe_required_file(client, app, tmp_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path / "root")
    app.config["FILE_SOURCES"] = [{"local_root": str(tmp_path / "root")}]
    admin = _admin()
    part = _released("PACK-UNSAFE", "A")
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"outside")
    PartFile(
        part_number=part.part_number,
        revision=part.revision,
        ext_group="pdf",
        ext="pdf",
        rel_path="../outside.pdf",
        path=str(outside),
    ).save()
    _login(client, admin)

    response = client.post(
        "/api/docpacks/build",
        json={
            "pn": part.part_number,
            "rev": part.revision,
            "selected_files": True,
            "file_types": ["pdf"],
        },
    )
    assert response.status_code == 403
    assert str(outside).encode() not in response.data


def test_excel_compile_cached_download_is_owner_bound(client, app, tmp_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILE_SOURCES"] = [{"local_root": str(tmp_path)}]
    owner = _admin("compile-owner@example.test")
    part = _released("COMPILE-BOUND", "A")
    _managed_file(tmp_path, part)
    _login(client, owner)

    response = client.post(
        "/tools/excelcompile",
        data={
            "file": (
                io.BytesIO(_compile_workbook(part.part_number, part.revision)),
                "compile.xlsx",
            ),
            "title": "../../not-a-physical-path",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    match = re.search(r'href="(/tools/excelcompile/download/([^"]+))"', body)
    assert match
    assert ".." not in match.group(2)

    intruder = _admin("compile-intruder@example.test")
    _login(client, intruder)
    assert client.get(match.group(1)).status_code == 404

    _login(client, owner)
    download = client.get(match.group(1))
    assert download.status_code == 200
    disposition = download.headers["Content-Disposition"]
    assert "not-a-physical-path" in disposition
    assert ".." not in disposition
    assert "/" not in disposition


def test_share_creation_uses_canonical_permission_and_exact_root(client):
    part = _released("SHARE-AUTH", "A")
    viewer = _user(
        "viewer-share-security@example.test",
        _standard_role("internal"),
    )
    _login(client, viewer)
    assert (
        client.post(
            f"/api/parts/{part.part_number}/shares",
            json={"rev": "A"},
        ).status_code
        == 403
    )

    creator = _user(
        "creator-share-security@example.test",
        _role(
            "creator-share-security",
            ["shares.create", "parts.read", "files.read"],
        ),
    )
    _login(client, creator)
    created = client.post(
        f"/api/parts/{part.part_number}/shares",
        json={"rev": "A"},
    )
    assert created.status_code == 200
    assert created.get_json()["share"]["revision"] == "A"
    assert (
        client.post(
            f"/api/parts/{part.part_number}/shares",
            json={"rev": "B"},
        ).status_code
        == 404
    )
    assert client.post(
        f"/api/parts/{part.part_number}/shares",
        json={"rev": "A", "allow_children": True},
    ).status_code == 403
    assert client.post(
        f"/api/parts/{part.part_number}/shares",
        json={"rev": "A", "allow_docpacks": True},
    ).status_code == 403


def test_blank_revision_share_is_exact_and_token_is_high_entropy(client, app):
    admin = _admin()
    blank = _released("SHARE-BLANK", "")
    _released("SHARE-BLANK", "A")
    _login(client, admin)
    first = _create_share(client, blank)
    second = _create_share(client, blank)
    assert first["share_token"] != second["share_token"]
    assert len(first["share_token"]) >= 40

    public = app.test_client()
    base = (
        f"/api/share/part/{first['share_id']}/{first['share_token']}"
        "/part_detail"
    )
    assert public.get(f"{base}?pn=SHARE-BLANK&rev=").status_code == 200
    assert public.get(f"{base}?pn=SHARE-BLANK&rev=A").status_code == 404


def test_public_token_state_and_authenticated_session_never_broaden_scope(
    client,
    app,
    monkeypatch,
):
    admin = _admin()
    part_a = _released("SHARE-TOKEN", "A")
    _released("SHARE-TOKEN", "B")
    _login(client, admin)
    created = _create_share(client, part_a)
    base = (
        f"/api/share/part/{created['share_id']}/"
        f"{created['share_token']}/part_detail"
    )
    public = app.test_client()

    assert public.get(f"{base}?pn=SHARE-TOKEN&rev=A").status_code == 200
    assert public.get(f"{base}?pn=SHARE-TOKEN&rev=B").status_code == 404
    assert (
        public.get(
            f"/api/share/part/{created['share_id']}/short/part_detail"
        ).status_code
        == 404
    )
    assert (
        public.get(
            f"/api/share/part/{ObjectId()}/"
            f"{created['share_token']}/part_detail"
        ).status_code
        == 404
    )

    _login(public, admin)
    assert public.get(f"{base}?pn=SHARE-TOKEN&rev=B").status_code == 404

    share = PartShareLink.objects(id=created["share_id"]).first()
    share.update(set__expires_at=utc_now() - timedelta(seconds=1))
    assert public.get(f"{base}?pn=SHARE-TOKEN&rev=A").status_code == 404
    share.update(
        set__expires_at=utc_now() + timedelta(days=1),
        set__enabled=False,
    )
    assert public.get(f"{base}?pn=SHARE-TOKEN&rev=A").status_code == 404

    monkeypatch.setattr(
        "app.views.part_shares.resolve_public_part_share_scope",
        lambda *_args, **_kwargs: (None, "unavailable"),
    )
    assert public.get(f"{base}?pn=SHARE-TOKEN&rev=A").status_code == 404


def test_public_child_and_file_scope_is_exact(client, app, tmp_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILE_SOURCES"] = [{"local_root": str(tmp_path)}]
    admin = _admin()
    root = _released("SHARE-ROOT", "A")
    child_a = _released("SHARE-CHILD", "A")
    child_b = _released("SHARE-CHILD", "B")
    BOMLink(
        parent_pn=root.part_number,
        parent_rev="A",
        child_pn=child_a.part_number,
        child_rev="A",
        qty=1,
    ).save()
    root_file = _managed_file(tmp_path, root, content=b"root")
    child_a_file = _managed_file(tmp_path, child_a, content=b"child-a")
    child_b_file = _managed_file(tmp_path, child_b, content=b"child-b")
    _login(client, admin)

    root_only = _create_share(client, root)
    public = app.test_client()
    root_prefix = (
        f"/share/part/{root_only['share_id']}/{root_only['share_token']}"
    )
    with app.app_context():
        root_file_token = file_token_for(root_file)
        child_a_file_token = file_token_for(child_a_file)
        child_b_file_token = file_token_for(child_b_file)
    assert public.get(
        f"{root_prefix}/files/{root_file_token}"
    ).status_code == 200
    assert public.get(
        f"{root_prefix}/files/{child_a_file_token}"
    ).status_code == 404
    flat = public.get(
        f"/api/share/part/{root_only['share_id']}/"
        f"{root_only['share_token']}/bom_flat?pn={root.part_number}&rev=A"
    )
    assert flat.status_code == 200
    assert flat.get_json() == []

    with_children = _create_share(client, root, allow_children=True)
    child_prefix = (
        f"/share/part/{with_children['share_id']}/"
        f"{with_children['share_token']}"
    )
    assert public.get(
        f"{child_prefix}/files/{child_a_file_token}"
    ).status_code == 200
    assert public.get(
        f"{child_prefix}/files/{child_b_file_token}"
    ).status_code == 404


def test_public_associated_files_and_internal_categories(client, app, tmp_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["EXTRA_FILES_ROOT"] = str(tmp_path)
    app.config["FILE_SOURCES"] = [{"local_root": str(tmp_path)}]
    admin = _admin()
    part = _released("SHARE-EXTRA", "A")
    _login(client, admin)
    created = _create_share(client, part)

    allowed_path = tmp_path / "extra" / "allowed.pdf"
    allowed_path.parent.mkdir(parents=True)
    allowed_path.write_bytes(b"allowed")
    allowed = PartExtraFile(
        part_number=part.part_number,
        revision=part.revision,
        original_name="allowed.pdf",
        rel_path="extra/allowed.pdf",
        source="upload",
    ).save()
    private_path = tmp_path / "extra" / "private.pdf"
    private_path.write_bytes(b"private")
    private = PartExtraFile(
        part_number=part.part_number,
        revision=part.revision,
        original_name="private.pdf",
        rel_path="extra/private.pdf",
        source="internal",
        label="Internal review",
    ).save()

    prefix = f"/share/part/{created['share_id']}/{created['share_token']}"
    public = app.test_client()
    with app.app_context():
        allowed_token = extra_file_token_for(allowed)
        private_token = extra_file_token_for(private)
    assert public.get(
        f"{prefix}/extra/{allowed_token}"
    ).status_code == 200
    assert public.get(
        f"{prefix}/extra/{private_token}"
    ).status_code == 404

    unsafe = PartExtraFile(
        part_number=part.part_number,
        revision=part.revision,
        original_name="unsafe.pdf",
        rel_path="../unsafe.pdf",
        source="upload",
    ).save()
    with app.app_context():
        unsafe_token = extra_file_token_for(unsafe)
    assert public.get(
        f"{prefix}/extra/{unsafe_token}"
    ).status_code == 404


def test_public_field_allowlist_and_token_audit_redaction(
    client,
    app,
    tmp_path,
):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILE_SOURCES"] = [{"local_root": str(tmp_path)}]
    admin = _admin()
    part = _released(
        "SHARE-FIELDS",
        "A",
        attrs={
            "material": "Steel",
            "internal_cost": "999",
            "payment_terms": "secret",
            "hidden_custom": "secret",
            "comments": [{"text": "private"}],
        },
    )
    _managed_file(tmp_path, part)
    _login(client, admin)
    created = _create_share(client, part, allow_attributes=True)
    public = app.test_client()
    response = public.get(
        f"/api/share/part/{created['share_id']}/"
        f"{created['share_token']}/part_detail"
        f"?pn={part.part_number}&rev={part.revision}"
    )
    assert response.status_code == 200
    serialized = json.dumps(response.get_json())
    for forbidden in (
        "internal_cost",
        "payment_terms",
        "hidden_custom",
        "private",
        str(tmp_path),
    ):
        assert forbidden not in serialized
    config_response = public.get(
        f"/api/share/part/{created['share_id']}/"
        f"{created['share_token']}/field-config"
    )
    assert config_response.status_code == 200
    config_serialized = json.dumps(config_response.get_json())
    assert "hidden_custom" not in config_serialized
    assert "approved_by" not in config_serialized

    overview = public.get(
        f"/api/share/part/{created['share_id']}/"
        f"{created['share_token']}/files_overview"
        f"?pn={part.part_number}&rev={part.revision}"
    )
    assert overview.status_code == 200
    overview_payload = overview.get_json()
    assert overview_payload["other_revisions"] == []
    assert str(tmp_path) not in json.dumps(overview_payload)
    assert created["share_token"] not in json.dumps(
        [entry.extra for entry in AuditLog.objects]
    )
    assert all(
        "token_prefix" not in (entry.extra or {})
        for entry in AuditLog.objects
    )


def test_public_docpack_rejects_arbitrary_options_and_revocation(client):
    admin = _admin()
    part = _released("SHARE-PACK", "A")
    _login(client, admin)
    created = _create_share(
        client,
        part,
        allow_docpacks=True,
        allow_attributes=True,
    )
    public = client.application.test_client()
    url = (
        f"/api/share/part/{created['share_id']}/"
        f"{created['share_token']}/docpacks/build"
    )
    assert public.post(
        url,
        json={
            "pn": part.part_number,
            "rev": part.revision,
            "whereused_report": True,
        },
    ).status_code == 400
    assert public.post(
        url,
        json={
            "pn": part.part_number,
            "rev": part.revision,
            "selected_files": True,
            "file_types": ["internal"],
        },
    ).status_code == 400

    assert client.delete(
        f"/api/parts/{part.part_number}/shares/{created['share_id']}"
    ).status_code == 200
    assert public.post(
        url,
        json={"pn": part.part_number, "rev": part.revision},
    ).status_code == 404


def test_legacy_share_migration_is_dry_run_and_unambiguous_only(app):
    with app.app_context():
        _released("LEGACY-ONE", "A")
        _released("LEGACY-MANY", "A")
        _released("LEGACY-MANY", "B")
        collection = PartShareLink._get_collection()
        one_id = ObjectId()
        many_id = ObjectId()
        for share_id, pn, raw_token in (
            (one_id, "LEGACY-ONE", "a" * 43),
            (many_id, "LEGACY-MANY", "b" * 43),
        ):
            collection.insert_one(
                {
                    "_id": share_id,
                    "part_number": pn,
                    "token_hash": hash_part_share_token(raw_token),
                    "token_prefix": raw_token[:8],
                    "enabled": True,
                }
            )

        runner = app.test_cli_runner()
        dry_run = runner.invoke(args=["share", "migrate-legacy"])
        assert dry_run.exit_code == 0
        assert "token_hash" not in dry_run.output
        assert "token_prefix" not in dry_run.output
        assert "revision" not in collection.find_one({"_id": one_id})
        public = app.test_client()
        assert public.get(
            f"/api/share/part/{many_id}/{'b' * 43}/part_detail"
            "?pn=LEGACY-MANY&rev=A"
        ).status_code == 404

        applied = runner.invoke(
            args=["share", "migrate-legacy", "--apply"]
        )
        assert applied.exit_code == 0
        assert collection.find_one({"_id": one_id})["revision"] == "A"
        assert "revision" not in collection.find_one({"_id": many_id})
