import csv
import io

from app.models.artifact import PartFile
from app.models.auth import Role, User
from app.models.bom import BOMLink
from app.models.part import Part


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()


def _admin_user():
    role = Role(name="admin").save()
    return User(
        email="arena-admin@example.com",
        password="test",
        active=True,
        fs_uniquifier="arena-admin-user",
        roles=[role],
    ).save()


def _read_csv_response(resp):
    text = resp.data.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def test_arena_bom_export_outputs_tree_rows_and_selected_fields(client):
    admin = _admin_user()
    _login(client, admin)

    root = Part(
        part_number="ASM-ARENA",
        revision="A",
        description="Arena Root",
        attrs={"material": "Steel", "category": "Assembly"},
    ).save()
    child = Part(
        part_number="CMP-ARENA",
        revision="B",
        description="Arena Child",
        attrs={"material": "Aluminium", "category": "Bracket"},
    ).save()
    grandchild = Part(
        part_number="SUB-ARENA",
        revision="C",
        description="Arena Grandchild",
        attrs={"material": "ABS", "category": "Detail"},
    ).save()

    BOMLink(parent_pn=root.part_number, parent_rev=root.revision, child_pn=child.part_number, child_rev=child.revision, qty=2).save()
    BOMLink(parent_pn=child.part_number, parent_rev=child.revision, child_pn=grandchild.part_number, child_rev=grandchild.revision, qty=3).save()

    resp = client.post(
        f"/api/parts/{root.part_number}/export/arena_bom",
        json={"rev": root.revision, "field_ids": ["revision", "material", "category", "description", "part_number"]},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.mimetype

    rows = _read_csv_response(resp)
    assert len(rows) == 3

    assert resp.headers["Content-Disposition"].endswith('ASM-ARENA_A_arena_bom.csv"') or "ASM-ARENA_A_arena_bom.csv" in resp.headers["Content-Disposition"]
    assert list(rows[0].keys()) == ["item number", "line number", "level", "quantity", "item name", "description", "Revision", "material", "item category"]

    assert rows[0]["item number"] == "ASM-ARENA"
    assert rows[0]["line number"] == "3"
    assert rows[0]["level"] == "0"
    assert rows[0]["quantity"] == "1"
    assert rows[0]["item name"] == "Arena Root"
    assert rows[0]["description"] == rows[0]["item name"]
    assert rows[0]["Revision"] == "A"
    assert rows[0]["material"] == "Steel"
    assert rows[0]["item category"] == "Assembly"

    assert rows[1]["item number"] == "CMP-ARENA"
    assert rows[1]["line number"] == "3"
    assert rows[1]["level"] == "1"
    assert rows[1]["quantity"] == "2"
    assert rows[1]["item name"] == "Arena Child"
    assert rows[1]["description"] == rows[1]["item name"]

    assert rows[2]["item number"] == "SUB-ARENA"
    assert rows[2]["line number"] == "3"
    assert rows[2]["level"] == "2"
    assert rows[2]["quantity"] == "3"
    assert rows[2]["item name"] == "Arena Grandchild"
    assert rows[2]["description"] == rows[2]["item name"]


def test_arena_bom_export_uses_aggregate_link_qty_not_source_occurrences(client):
    admin = _admin_user()
    _login(client, admin)

    root = Part(part_number="ASM-OCC", revision="A", description="Root").save()
    child = Part(part_number="SUB-OCC", revision="A", description="Subassembly").save()
    grandchild = Part(part_number="CMP-OCC", revision="A", description="Component").save()

    BOMLink(
        parent_pn=root.part_number,
        parent_rev=root.revision,
        child_pn=child.part_number,
        child_rev=child.revision,
        qty=2,
        occurrences=[{"seq": 1, "qty": 1}, {"seq": 2, "qty": 1}],
    ).save()
    BOMLink(
        parent_pn=child.part_number,
        parent_rev=child.revision,
        child_pn=grandchild.part_number,
        child_rev=grandchild.revision,
        qty=3,
        occurrences=[{"seq": 1, "qty": 3}],
    ).save()

    resp = client.post(
        f"/api/parts/{root.part_number}/export/arena_bom",
        json={"rev": root.revision, "field_ids": ["total_qty"]},
    )
    assert resp.status_code == 200

    rows = _read_csv_response(resp)
    assert [row["item number"] for row in rows] == ["ASM-OCC", "SUB-OCC", "CMP-OCC"]
    assert [row["quantity"] for row in rows] == ["1", "2", "3"]
    assert rows[2]["Total Qty"] == "6"


def test_arena_bom_export_preserves_fractional_quantity_precision(client):
    admin = _admin_user()
    _login(client, admin)

    root = Part(part_number="ASM-FRACTION", revision="A", description="Root").save()
    child = Part(part_number="CMP-FRACTION", revision="A", description="Component").save()
    BOMLink(
        parent_pn=root.part_number,
        parent_rev=root.revision,
        child_pn=child.part_number,
        child_rev=child.revision,
        qty=0.125,
    ).save()

    resp = client.post(
        f"/api/parts/{root.part_number}/export/arena_bom",
        json={"rev": root.revision},
    )
    assert resp.status_code == 200
    rows = _read_csv_response(resp)
    assert rows[1]["quantity"] == "0.125"


def test_arena_bom_export_uses_admin_defaults_and_alias_headers(client):
    admin = _admin_user()
    _login(client, admin)

    config_resp = client.put(
        "/api/admin/field-config",
        json={
            "builtin_fields": [
                {"id": "revision", "label": "Revision", "arena_header": "Arena Revision"},
                {"id": "material", "label": "Material", "arena_header": "Arena Material"},
            ],
            "custom_fields": [
                {
                    "id": "legacy_code",
                    "label": "Legacy Code",
                    "arena_header": "Legacy Arena Code",
                    "source_path": "attrs.Legacy Code",
                    "data_type": "text",
                },
            ],
            "contexts": {
                "arena_bom": {
                    "allowed_field_ids": ["revision", "material", "legacy_code"],
                    "default_field_ids": ["revision", "material", "legacy_code"],
                }
            },
        },
    )
    assert config_resp.status_code == 200

    field_config = client.get("/api/field-config").get_json()["config"]
    fields_by_id = {field["id"]: field for field in field_config["fields"]}
    assert fields_by_id["revision"]["arena_header"] == "Arena Revision"
    assert fields_by_id["material"]["arena_header"] == "Arena Material"
    assert fields_by_id["legacy_code"]["arena_header"] == "Legacy Arena Code"

    root = Part(
        part_number="ASM-ALIAS",
        revision="A",
        description="Arena Alias Root",
        attrs={"material": "Steel", "Legacy Code": "LEG-ROOT"},
    ).save()
    child = Part(
        part_number="CMP-ALIAS",
        revision="B",
        description="Arena Alias Child",
        attrs={"material": "Brass", "Legacy Code": "LEG-CHILD"},
    ).save()
    BOMLink(parent_pn=root.part_number, parent_rev=root.revision, child_pn=child.part_number, child_rev=child.revision, qty=4).save()

    resp = client.post(
        f"/api/parts/{root.part_number}/export/arena_bom",
        json={"rev": root.revision},
    )
    assert resp.status_code == 200

    rows = _read_csv_response(resp)
    assert list(rows[0].keys()) == [
        "item number",
        "line number",
        "level",
        "quantity",
        "item name",
        "description",
        "Arena Revision",
        "Arena Material",
        "Legacy Arena Code",
    ]

    assert rows[0]["item number"] == "ASM-ALIAS"
    assert rows[0]["Arena Revision"] == "A"
    assert rows[0]["Arena Material"] == "Steel"
    assert rows[0]["Legacy Arena Code"] == "LEG-ROOT"

    assert rows[1]["item number"] == "CMP-ALIAS"
    assert rows[1]["quantity"] == "4"
    assert rows[1]["Arena Revision"] == "B"
    assert rows[1]["Arena Material"] == "Brass"
    assert rows[1]["Legacy Arena Code"] == "LEG-CHILD"


def test_arena_file_links_export_builds_base_prefixed_rows(client):
    admin = _admin_user()
    _login(client, admin)

    root = Part(part_number="ASM-LINK", revision="A", description="Root").save()
    child = Part(part_number="CMP-LINK", revision="B", description="Child").save()
    BOMLink(parent_pn=root.part_number, parent_rev=root.revision, child_pn=child.part_number, child_rev=child.revision, qty=1).save()

    PartFile(
        part_number=root.part_number,
        revision=root.revision,
        ext_group="pdf",
        ext="pdf",
        rel_path="deliverables/ASM-LINK_REV_A.pdf",
        path="C:/arena/ASM-LINK_REV_A.pdf",
    ).save()
    PartFile(
        part_number=child.part_number,
        revision=child.revision,
        ext_group="dxf",
        ext="dxf",
        rel_path="deliverables/CMP-LINK_REV_B.dxf",
        path="C:/arena/CMP-LINK_REV_B.dxf",
    ).save()
    PartFile(
        part_number=child.part_number,
        revision=child.revision,
        ext_group="step",
        ext="stp",
        rel_path="deliverables/CMP-LINK_REV_B.stp",
        path="C:/arena/CMP-LINK_REV_B.stp",
    ).save()

    resp = client.post(
        f"/api/parts/{root.part_number}/export/arena_file_links",
        json={"rev": root.revision, "base_url": "https://example.com/arena"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.mimetype

    rows = _read_csv_response(resp)
    assert len(rows) == 3

    by_key = {(row["item number"], row["file format"]): row for row in rows}

    root_pdf = by_key[(root.part_number, "pdf")]
    assert root_pdf["file title"] == "ASM-LINK_REV_A.pdf"
    assert root_pdf["file location"] == "https://example.com/arena/PDF/ASM-LINK_REV_A.pdf"
    assert root_pdf["file active"] == "1"
    assert root_pdf["file category"] == "Drawing"
    assert root_pdf["edition identifier"] == "A"

    child_dxf = by_key[(child.part_number, "dxf")]
    assert child_dxf["file title"] == "CMP-LINK_REV_B.dxf"
    assert child_dxf["file location"] == "https://example.com/arena/DXF/CMP-LINK_REV_B.dxf"
    assert child_dxf["file active"] == "0"
    assert child_dxf["file category"] == "CAD File"

    child_step = by_key[(child.part_number, "step")]
    assert child_step["file title"] == "CMP-LINK_REV_B.stp"
    assert child_step["file location"] == "https://example.com/arena/STEP/CMP-LINK_REV_B.step"
    assert child_step["file description"] == "CMP-LINK_REV_B"
