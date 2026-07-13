from datetime import datetime

from app.models.artifact import PartFile
from app.models.app_settings import AppSettings
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

    Part.objects(id=cold.id).update(unset__has_stl=1)
    missing_flag_resp = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {"has_stl": {"value": False}}},
    )
    assert missing_flag_resp.status_code == 200
    assert any(row["part_number"] == "FLT-200" for row in missing_flag_resp.get_json()["data"])


def test_parts_lazy_filters_approved_column_true_false_and_any(client):
    admin = _admin_user()
    _login(client, admin)

    Part(part_number="APR-100", revision="A", description="Approved", attrs={"approvedby": "QA"}).save()
    Part(part_number="APR-200", revision="A", description="Pending", attrs={}).save()
    Part(part_number="APR-250", revision="A", description="Placeholder raw", attrs={"approved": "Approved"}).save()
    Part(
        part_number="APR-300",
        revision="A",
        description="Placeholder canonical",
        canonical={"approved_by": "Approved By"},
    ).save()

    approved_resp = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {"approved": {"value": True}}},
    )
    assert approved_resp.status_code == 200
    approved_rows = approved_resp.get_json()["data"]
    assert [row["part_number"] for row in approved_rows] == ["APR-100", "APR-250"]

    unapproved_resp = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {"approved": {"value": False}}},
    )
    assert unapproved_resp.status_code == 200
    unapproved_rows = unapproved_resp.get_json()["data"]
    assert [row["part_number"] for row in unapproved_rows] == ["APR-200", "APR-300"]

    any_resp = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {}},
    )
    assert any_resp.status_code == 200
    assert [row["part_number"] for row in any_resp.get_json()["data"]] == [
        "APR-100",
        "APR-200",
        "APR-250",
        "APR-300",
    ]


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


def test_parts_lazy_honors_match_modes_and_multiple_constraints(client):
    admin = _admin_user()
    _login(client, admin)

    Part(part_number="MODE-100", revision="A", description="Alpha fixture plate").save()
    Part(part_number="MODE-200", revision="A", description="Beta fixture bracket").save()
    Part(part_number="MODE-300", revision="A", description="Alpha cover").save()

    and_resp = client.post(
        "/api/parts_lazy",
        json={
            "first": 0,
            "rows": 25,
            "filters": {
                "description": {
                    "operator": "and",
                    "constraints": [
                        {"value": "fixture", "matchMode": "contains"},
                        {"value": "Alpha", "matchMode": "startsWith"},
                    ],
                }
            },
        },
    )
    assert [row["part_number"] for row in and_resp.get_json()["data"]] == ["MODE-100"]

    or_resp = client.post(
        "/api/parts_lazy",
        json={
            "first": 0,
            "rows": 25,
            "filters": {
                "description": {
                    "operator": "or",
                    "constraints": [
                        {"value": "bracket", "matchMode": "endsWith"},
                        {"value": "Alpha cover", "matchMode": "equals"},
                    ],
                }
            },
        },
    )
    assert [row["part_number"] for row in or_resp.get_json()["data"]] == ["MODE-200", "MODE-300"]


def test_parts_lazy_filters_typed_custom_dates_and_creates_active_index(client):
    admin = _admin_user()
    _login(client, admin)
    save_field_config(
        {
            "custom_fields": [
                {"id": "eta_date", "label": "ETA Date", "source_path": "attrs.eta_date", "data_type": "date"},
            ],
            "contexts": {
                "parts_list": {
                    "allowed_field_ids": ["part_number", "eta_date"],
                    "default_field_ids": ["part_number", "eta_date"],
                }
            },
        }
    )
    Part(part_number="DATE-100", revision="A", attrs={"eta_date": "2026-07-01"}).save()
    Part(part_number="DATE-200", revision="A", attrs={"eta_date": "2026-07-15"}).save()
    Part(part_number="DATE-300", revision="A", attrs={}).save()

    stored = Part.objects(part_number="DATE-100").first()
    assert isinstance(stored.field_values["eta_date"], datetime)

    response = client.post(
        "/api/parts_lazy",
        json={
            "first": 0,
            "rows": 25,
            "sortField": "eta_date",
            "filters": {
                "eta_date": {
                    "operator": "and",
                    "constraints": [{"value": "2026-07-01", "matchMode": "dateAfter"}],
                }
            },
        },
    )
    assert response.status_code == 200
    assert [row["part_number"] for row in response.get_json()["data"]] == ["DATE-200"]
    assert response.get_json()["data"][0]["eta_date"] == "2026-07-15"
    assert "parts_field_values_eta_date_idx" in Part._get_collection().index_information()

    empty_response = client.post(
        "/api/parts_lazy",
        json={
            "first": 0,
            "rows": 25,
            "filters": {
                "eta_date": {
                    "operator": "and",
                    "constraints": [{"value": None, "matchMode": "isEmpty"}],
                }
            },
        },
    )
    assert [row["part_number"] for row in empty_response.get_json()["data"]] == ["DATE-300"]


def test_parts_lazy_global_search_matches_part_number_and_description_with_other_filters(client):
    admin = _admin_user()
    _login(client, admin)

    Part(part_number="INV-100", revision="A", description="Fixture Plate", attrs={"approvedby": "QA"}).save()
    Part(part_number="INV-200", revision="A", description="Fixture Plate", attrs={}).save()
    Part(part_number="FIX-300", revision="A", description="Inventory Bracket", attrs={"approvedby": "QA"}).save()

    resp = client.post(
        "/api/parts_lazy",
        json={
            "first": 0,
            "rows": 25,
            "filters": {
                "global": {"value": "inv fixture"},
                "approved": {"value": True},
            },
        },
    )
    assert resp.status_code == 200
    rows = resp.get_json()["data"]
    assert [row["part_number"] for row in rows] == ["INV-100"]


def test_parts_lazy_global_search_matches_materialized_notes_and_comments(client):
    admin = _admin_user()
    _login(client, admin)
    Part(part_number="ANNOT-100", revision="A", description="Plain part").save()
    Part(part_number="ANNOT-200", revision="A", description="Plain part").save()
    Part.objects(part_number="ANNOT-100").update(set__notes_search="Inspect the sealing face")
    Part.objects(part_number="ANNOT-200").update(set__comments_search="Replace the mounting bracket")

    notes_resp = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {"global": {"value": "sealing face"}}},
    )
    assert [row["part_number"] for row in notes_resp.get_json()["data"]] == ["ANNOT-100"]

    comments_resp = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {"global": {"value": "mounting bracket"}}},
    )
    assert [row["part_number"] for row in comments_resp.get_json()["data"]] == ["ANNOT-200"]


def test_parts_lazy_combines_approved_file_and_material_column_filters(client):
    admin = _admin_user()
    _login(client, admin)

    matching = Part(
        part_number="MULTI-100",
        revision="A",
        description="Matching part",
        attrs={"approvedby": "QA", "material": "Aluminium 6061"},
    ).save()
    Part(
        part_number="MULTI-200",
        revision="A",
        description="Wrong material",
        attrs={"approvedby": "QA", "material": "Mild steel"},
    ).save()
    Part(
        part_number="MULTI-300",
        revision="A",
        description="Not approved",
        attrs={"material": "Aluminium 6061"},
    ).save()
    _part_file(matching.part_number, matching.revision, "pdf", "pdf")

    response = client.post(
        "/api/parts_lazy",
        json={
            "first": 0,
            "rows": 25,
            "filters": {
                "approved": {"value": True},
                "has_pdf": {"value": True},
                "material": {"value": "aluminium"},
            },
        },
    )

    assert response.status_code == 200
    assert [row["part_number"] for row in response.get_json()["data"]] == ["MULTI-100"]


def test_parts_lazy_clamps_and_validates_pagination(client):
    admin = _admin_user()
    _login(client, admin)
    Part.objects.insert(
        [Part(part_number=f"PAGE-{index:03d}", revision="A") for index in range(105)],
        load_bulk=False,
    )

    malformed = client.post("/api/parts_lazy", json={"first": "bad", "rows": "bad", "filters": {}})
    assert malformed.status_code == 200
    assert len(malformed.get_json()["data"]) == 25
    assert malformed.get_json()["data"][0]["part_number"] == "PAGE-000"

    non_positive = client.post("/api/parts_lazy", json={"first": -20, "rows": 0, "filters": {}})
    assert non_positive.status_code == 200
    assert len(non_positive.get_json()["data"]) == 25
    assert non_positive.get_json()["data"][0]["part_number"] == "PAGE-000"

    oversized = client.post("/api/parts_lazy", json={"first": 0, "rows": 500, "filters": {}})
    assert oversized.status_code == 200
    assert len(oversized.get_json()["data"]) == 100


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


def test_final_approval_state_is_exposed_and_filterable_across_part_views(client):
    admin = _admin_user()
    _login(client, admin)

    approved_parent = Part(
        part_number="APR-VIEW-PARENT-YES",
        revision="A",
        description="Approved parent",
        attrs={"approvedby": "QA Person"},
    ).save()
    unapproved_parent = Part(
        part_number="APR-VIEW-PARENT-NO",
        revision="A",
        description="Unapproved parent",
        attrs={"approvedby": "Approver"},
    ).save()
    approved_child = Part(
        part_number="APR-VIEW-CHILD-YES",
        revision="A",
        description="Approved child",
        attrs={"approvedby": "QA Person"},
    ).save()
    unapproved_child = Part(
        part_number="APR-VIEW-CHILD-NO",
        revision="A",
        description="Unapproved child",
        attrs={"approvedby": "Approver"},
    ).save()
    target = Part(part_number="APR-VIEW-TARGET", revision="A", description="Where-used target").save()

    for child in (approved_child, unapproved_child, target):
        BOMLink(
            parent_pn=approved_parent.part_number,
            parent_rev=approved_parent.revision,
            child_pn=child.part_number,
            child_rev=child.revision,
            qty=1,
        ).save()
    BOMLink(
        parent_pn=unapproved_parent.part_number,
        parent_rev=unapproved_parent.revision,
        child_pn=target.part_number,
        child_rev=target.revision,
        qty=1,
    ).save()

    config_resp = client.get("/api/field-config")
    assert config_resp.status_code == 200
    contexts = config_resp.get_json()["config"]["contexts"]
    for context_name in ("parts_list", "part_detail_summary", "bom_tree", "where_used"):
        assert "approved" in contexts[context_name]["allowed_field_ids"]

    bom_resp = client.get(
        f"/api/bom_tree?parent={approved_parent.part_number}&parent_rev={approved_parent.revision}"
    )
    assert bom_resp.status_code == 200
    bom_approval = {node["data"]["part_number"]: node["data"]["approved"] for node in bom_resp.get_json()}
    assert bom_approval[approved_child.part_number] is True
    assert bom_approval[unapproved_child.part_number] is False

    approved_wu = client.post(
        "/api/whereused_lazy",
        json={
            "pn": target.part_number,
            "rev": target.revision,
            "first": 0,
            "rows": 25,
            "filters": {"approved": {"value": True}},
        },
    )
    assert approved_wu.status_code == 200
    assert [row["part_number"] for row in approved_wu.get_json()["data"]] == [approved_parent.part_number]

    unapproved_wu = client.post(
        "/api/whereused_lazy",
        json={
            "pn": target.part_number,
            "rev": target.revision,
            "first": 0,
            "rows": 25,
            "filters": {"approved": {"value": False}},
        },
    )
    assert unapproved_wu.status_code == 200
    assert [row["part_number"] for row in unapproved_wu.get_json()["data"]] == [unapproved_parent.part_number]

    detail_resp = client.get(f"/api/part_detail?pn={target.part_number}&rev={target.revision}")
    assert detail_resp.status_code == 200
    detail = detail_resp.get_json()
    assert detail["part"]["field_values"]["approved"] is False
    used_in_approval = {row["part_number"]: row["approved"] for row in detail["whereused"]}
    assert used_in_approval == {
        approved_parent.part_number: True,
        unapproved_parent.part_number: False,
    }


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

    settings = AppSettings.objects().first()
    assert settings is not None
    assert "purchase" in (settings.process_meta or {})
    assert settings.process_meta["coating"]["icon"] == "spray.svg"
    assert settings.process_meta["coating"]["color"] == "1, 2, 3"
    assert settings.process_meta["coating"]["aliases"] == ["powder coat", "paint shop"]
    assert settings.process_meta["coating"]["file_groups"] == ["pdf", "datasheet"]

    page = client.get("/admin/settings")
    assert page.status_code == 200
    body = page.data.decode("utf-8")
    assert 'value="coating"' in body
    assert 'value="powder coat, paint shop"' in body

    meta_resp = client.get("/api/process_meta")
    assert meta_resp.status_code == 200
    meta = meta_resp.get_json()
    assert "purchase" in meta
    assert meta["coating"]["icon"] == "spray.svg"
    assert meta["coating"]["color"] == "1, 2, 3"
    assert meta["coating"]["aliases"] == ["powder coat", "paint shop"]
    assert meta["coating"]["file_groups"] == ["pdf", "datasheet"]

    reset_resp = client.post("/admin/settings", data={"reset_process_library": "1"})
    assert reset_resp.status_code == 302

    settings.reload()
    assert settings.process_meta == {}

    reset_meta = client.get("/api/process_meta").get_json()
    assert "coating" not in reset_meta
    assert "purchase" in reset_meta


def test_admin_settings_recompute_reclassifies_existing_parts_with_custom_process(client):
    admin = _admin_user()
    _login(client, admin)

    with client.application.app_context():
        part = Part(part_number="ANO-100", revision="A", description="Bracket", attrs={"process": "anodizing"}).save()
    part.reload()
    assert part.processes == ["others"]
    assert (part.canonical or {}).get("processes") == ["others"]

    resp = client.post(
        "/admin/settings",
        data={
            "process_name": ["anodising"],
            "process_icon": ["unknown.svg"],
            "process_color": ["118, 113, 113"],
            "process_aliases": ["anodize, anodizing"],
            "process_file_groups": ["pdf"],
            "recompute_process_library": "1",
        },
    )
    assert resp.status_code == 302

    part.reload()
    assert part.processes == ["anodising"]
    assert (part.canonical or {}).get("processes") == ["anodising"]
