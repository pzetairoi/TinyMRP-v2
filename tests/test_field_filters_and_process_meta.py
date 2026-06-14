from app.models.artifact import PartFile
from app.models.auth import Role, User
from app.models.bom import BOMLink
from app.models.part import Part
from app.services.field_config import save_field_config


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()


def _admin_user():
    role = Role(name="admin").save()
    return User(
        email="admin-filters@example.com",
        password="test",
        active=True,
        fs_uniquifier="admin-field-filters",
        roles=[role],
    ).save()


def _part_file(pn: str, rev: str, group: str, ext: str):
    PartFile(
        part_number=pn,
        revision=rev,
        ext_group=group,
        ext=ext,
        rel_path=f"{group}/{pn}_REV_{rev}.{ext}" if rev else f"{group}/{pn}.{ext}",
        path=f"C:/vault/{group}/{pn}_REV_{rev}.{ext}" if rev else f"C:/vault/{group}/{pn}.{ext}",
    ).save()


def test_parts_lazy_filters_custom_boolean_number_and_file_fields(client):
    admin = _admin_user()
    _login(client, admin)

    save_field_config(
        {
            "custom_fields": [
                {"id": "flammable", "label": "Flammable", "source_path": "attrs.flammable", "data_type": "boolean"},
                {"id": "density_score", "label": "Density Score", "source_path": "attrs.density_score", "data_type": "number"},
            ],
            "contexts": {
                "parts_list": {
                    "allowed_field_ids": ["part_number", "description", "flammable", "density_score", "has_stl"],
                    "default_field_ids": ["part_number", "description", "flammable", "density_score", "has_stl"],
                }
            },
        }
    )

    hot = Part(part_number="FLT-100", revision="A", description="Hot part", attrs={"flammable": True, "density_score": 12.5}).save()
    cold = Part(part_number="FLT-200", revision="A", description="Cold part", attrs={"flammable": False, "density_score": 4.2}).save()
    _part_file(hot.part_number, hot.revision, "stl", "stl")

    resp_true = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {"flammable": {"value": "true"}, "density_score": {"value": ">10"}, "has_stl": {"value": "true"}}},
    )
    assert resp_true.status_code == 200
    rows = resp_true.get_json()["data"]
    assert [row["part_number"] for row in rows] == ["FLT-100"]

    resp_false = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {"has_stl": {"value": False}}},
    )
    assert resp_false.status_code == 200
    rows_false = resp_false.get_json()["data"]
    assert any(row["part_number"] == "FLT-200" for row in rows_false)
    assert all(row["part_number"] != "FLT-100" for row in rows_false)


def test_parts_lazy_filters_approved_from_checkbox_and_string_false(client):
    admin = _admin_user()
    _login(client, admin)

    Part(part_number="APR-100", revision="A", description="Approved", attrs={"approvedby": "QA"}).save()
    Part(part_number="APR-200", revision="A", description="Pending", attrs={}).save()

    approved_resp = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {"approved_only": {"value": True}}},
    )
    assert approved_resp.status_code == 200
    approved_rows = approved_resp.get_json()["data"]
    assert [row["part_number"] for row in approved_rows] == ["APR-100"]

    unapproved_resp = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {"approved": {"value": False}}},
    )
    assert unapproved_resp.status_code == 200
    unapproved_rows = unapproved_resp.get_json()["data"]
    assert [row["part_number"] for row in unapproved_rows] == ["APR-200"]


def test_parts_lazy_supports_constraint_style_filter_payloads(client):
    admin = _admin_user()
    _login(client, admin)

    Part(part_number="CST-100", revision="A", description="Approved", attrs={"approvedby": "QA"}).save()
    Part(part_number="CST-200", revision="A", description="Pending", attrs={}).save()

    resp = client.post(
        "/api/parts_lazy",
        json={
            "first": 0,
            "rows": 25,
            "filters": {
                "approved": {
                    "operator": "and",
                    "constraints": [{"value": False, "matchMode": "equals"}],
                }
            },
        },
    )
    assert resp.status_code == 200
    rows = resp.get_json()["data"]
    assert [row["part_number"] for row in rows] == ["CST-200"]


def test_bom_tree_and_whereused_include_extended_file_availability(client):
    admin = _admin_user()
    _login(client, admin)

    root = Part(part_number="ASM-FILES", revision="A", description="Assembly").save()
    child = Part(part_number="CMP-FILES", revision="B", description="Component").save()
    BOMLink(parent_pn=root.part_number, parent_rev=root.revision, child_pn=child.part_number, child_rev=child.revision, qty=2).save()
    _part_file(root.part_number, root.revision, "pdf", "pdf")
    _part_file(child.part_number, child.revision, "stl", "stl")

    root_resp = client.get(f"/api/bom_tree?pn={root.part_number}&rev={root.revision}")
    assert root_resp.status_code == 200
    root_nodes = root_resp.get_json()
    assert root_nodes[0]["data"]["has_pdf"] is True

    child_resp = client.get(f"/api/bom_tree?parent={root.part_number}&parent_rev={root.revision}")
    assert child_resp.status_code == 200
    child_nodes = child_resp.get_json()
    assert child_nodes[0]["data"]["has_stl"] is True

    wu_resp = client.post(
        "/api/whereused_lazy",
        json={"pn": child.part_number, "rev": child.revision, "first": 0, "rows": 25, "filters": {"has_pdf": {"value": "true"}}},
    )
    assert wu_resp.status_code == 200
    wu_rows = wu_resp.get_json()["data"]
    assert len(wu_rows) == 1
    assert wu_rows[0]["part_number"] == root.part_number
    assert wu_rows[0]["has_pdf"] is True


def test_bom_flat_aggregates_duplicate_descendants(client):
    admin = _admin_user()
    _login(client, admin)

    root = Part(part_number="ASM-FLAT", revision="A", description="Assembly").save()
    sub = Part(part_number="SUB-FLAT", revision="A", description="Sub Assembly").save()
    child = Part(part_number="CMP-FLAT", revision="B", description="Shared Component").save()

    BOMLink(parent_pn=root.part_number, parent_rev=root.revision, child_pn=sub.part_number, child_rev=sub.revision, qty=1).save()
    BOMLink(parent_pn=root.part_number, parent_rev=root.revision, child_pn=child.part_number, child_rev=child.revision, qty=2).save()
    BOMLink(parent_pn=sub.part_number, parent_rev=sub.revision, child_pn=child.part_number, child_rev=child.revision, qty=3).save()

    resp = client.get(f"/api/bom_flat?pn={root.part_number}&rev={root.revision}")
    assert resp.status_code == 200
    rows = resp.get_json()

    by_pn = {row["part_number"]: row for row in rows}
    assert sorted(by_pn.keys()) == [child.part_number, sub.part_number]
    assert by_pn[sub.part_number]["qty"] == 1
    assert by_pn[child.part_number]["qty"] == 5
    assert by_pn[child.part_number]["revision"] == child.revision


def test_admin_settings_can_override_and_reset_process_library(client):
    admin = _admin_user()
    _login(client, admin)

    resp = client.post(
        "/admin/settings",
        data={
            "process_name": ["coating", "others"],
            "process_icon": ["spray.svg", "unknown.svg"],
            "process_color": ["1, 2, 3", "118, 113, 113"],
            "process_aliases": ["powder coat, paint shop", ""],
            "process_file_groups": ["pdf, datasheet", ""],
        },
    )
    assert resp.status_code == 302

    meta_resp = client.get("/api/process_meta")
    assert meta_resp.status_code == 200
    meta = meta_resp.get_json()
    assert meta["coating"]["icon"] == "spray.svg"
    assert meta["coating"]["color"] == "1, 2, 3"
    assert meta["coating"]["aliases"] == ["powder coat", "paint shop"]
    assert meta["coating"]["file_groups"] == ["pdf", "datasheet"]

    reset_resp = client.post("/admin/settings", data={"reset_process_library": "1"})
    assert reset_resp.status_code == 302

    reset_meta = client.get("/api/process_meta").get_json()
    assert "coating" not in reset_meta
    assert "purchase" in reset_meta
