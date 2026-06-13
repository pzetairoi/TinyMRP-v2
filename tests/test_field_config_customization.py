import io
import zipfile

from openpyxl import load_workbook

from app.models.auth import Role, User
from app.models.bom import BOMLink
from app.models.part import Part
from app.services.docpacks import DocPackOptions, build_docpack
from app.services.field_config import save_field_config


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()


def _admin_user():
    role = Role(name="admin").save()
    return User(
        email="admin@example.com",
        password="test",
        active=True,
        fs_uniquifier="admin-field-config",
        roles=[role],
    ).save()


def _config_payload():
    return {
        "builtin_fields": [
            {"id": "description", "label": "Description", "source_path": "attrs.summary_text"},
            {"id": "material", "label": "Material", "source_path": "attrs.mat_code"},
        ],
        "custom_fields": [
            {"id": "legacy_code", "label": "Legacy Code", "source_path": "attrs.legacy_code", "data_type": "text"},
        ],
        "contexts": {
            "parts_list": {
                "allowed_field_ids": [
                    "thumbnail",
                    "part_number",
                    "revision",
                    "description",
                    "material",
                    "legacy_code",
                ],
                "default_field_ids": [
                    "part_number",
                    "description",
                    "material",
                    "legacy_code",
                ],
            },
            "part_detail_summary": {
                "allowed_field_ids": ["description", "material", "legacy_code"],
                "default_field_ids": ["description", "material", "legacy_code"],
            },
            "excel_bom": {
                "allowed_field_ids": [
                    "part_number",
                    "revision",
                    "description",
                    "total_qty",
                    "legacy_code",
                ],
                "default_field_ids": [
                    "part_number",
                    "revision",
                    "description",
                    "total_qty",
                    "legacy_code",
                ],
            },
        },
    }


def test_field_config_api_and_user_preferences(client):
    admin = _admin_user()
    _login(client, admin)

    resp = client.put("/api/admin/field-config", json=_config_payload())
    assert resp.status_code == 200

    get_resp = client.get("/api/field-config")
    assert get_resp.status_code == 200
    data = get_resp.get_json()
    assert data["ok"] is True
    assert data["permissions"]["can_admin"] is True
    parts_ctx = data["config"]["contexts"]["parts_list"]
    assert "legacy_code" in parts_ctx["allowed_field_ids"]
    desc_field = next(field for field in data["config"]["fields"] if field["id"] == "description")
    assert desc_field["source_path"] == "attrs.summary_text"

    prefs_resp = client.put(
        "/api/me/settings",
        json={"field_preferences": {"contexts": {"parts_list": {"field_ids": ["legacy_code", "part_number"]}}}},
    )
    assert prefs_resp.status_code == 200
    prefs_data = prefs_resp.get_json()
    assert prefs_data["settings"]["field_preferences"]["contexts"]["parts_list"]["field_ids"] == ["legacy_code", "part_number"]


def test_parts_and_part_detail_use_custom_field_mapping(client):
    admin = _admin_user()
    _login(client, admin)
    client.put("/api/admin/field-config", json=_config_payload())

    part = Part(
        part_number="CFG-100",
        revision="A",
        description="Legacy Description",
        attrs={"summary_text": "Mapped Description", "mat_code": "SS304", "legacy_code": "LEG-100"},
    ).save()

    list_resp = client.post("/api/parts_lazy", json={"first": 0, "rows": 25, "filters": {}})
    assert list_resp.status_code == 200
    rows = list_resp.get_json()["data"]
    row = next(item for item in rows if item["part_number"] == "CFG-100")
    assert row["description"] == "Mapped Description"
    assert row["material"] == "SS304"
    assert row["legacy_code"] == "LEG-100"

    detail_resp = client.get(f"/api/part_detail?pn={part.part_number}&rev={part.revision}")
    assert detail_resp.status_code == 200
    detail = detail_resp.get_json()
    assert detail["part"]["description"] == "Mapped Description"
    assert detail["part"]["field_values"]["legacy_code"] == "LEG-100"
    assert detail["part"]["field_values"]["material"] == "SS304"


def test_excel_bom_respects_selected_field_ids(app):
    root = Part(part_number="ASM-FLD", revision="", description="Root").save()
    child = Part(
        part_number="CMP-FLD",
        revision="B",
        description="Legacy Child",
        attrs={"summary_text": "Mapped Child", "legacy_code": "LC-77"},
    ).save()
    BOMLink(parent_pn=root.part_number, parent_rev="", child_pn=child.part_number, child_rev="B", qty=3).save()

    with app.app_context():
        save_field_config(_config_payload())
        _, data, mime = build_docpack(
            DocPackOptions(
                root_pn=root.part_number,
                root_rev="",
                depth="full",
                include_consumed=True,
                want_excel_bom=True,
                excel_field_ids=["part_number", "revision", "description", "legacy_code", "total_qty"],
                want_selected_files=False,
                want_pdf_binder=False,
                want_visual_list=False,
            )
        )

    assert mime == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(data))
    bom_name = next(name for name in zf.namelist() if name.lower().endswith(".xlsx"))
    wb = load_workbook(io.BytesIO(zf.read(bom_name)))
    ws = wb.active
    header = [str(c.value or "").strip() for c in next(ws.iter_rows(min_row=1, max_row=1))]
    data_row = [str(c.value or "").strip() for c in next(ws.iter_rows(min_row=3, max_row=3))]

    assert header == ["Part Number", "Revision", "Description", "Legacy Code", "Total Qty"]
    assert "Mapped Child" in data_row
    assert "LC-77" in data_row
