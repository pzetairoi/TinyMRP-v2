from app.models.auth import Role
from app.models.part import Part
from app.models.bom import BOMLink
from app.models.artifact import PartFile


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def test_part_insights_shape(client, user):
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

    part = Part(
        part_number="HW-55",
        revision="",
        description="Washer",
        processes=["hardware"],
        attrs={"material": "Steel", "approvedby": "QA Person"},
    ).save()
    Part(
        part_number="ASM-500",
        revision="",
        description="Assembly",
        attrs={"approvedby": "QA Person"},
    ).save()
    BOMLink(parent_pn="ASM-500", parent_rev="", child_pn=part.part_number, child_rev="", qty=3).save()
    PartFile(
        part_number=part.part_number,
        revision="",
        ext_group="pdf",
        ext="pdf",
        rel_path="HW-55.pdf",
        path="C:/tmp/HW-55.pdf",
    ).save()

    resp = client.get(f"/api/parts/{part.part_number}/insights?rev=")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["classification"] == "hardware"
    assert data["deliverables_present"]["pdf"] is True
    assert "material" not in data["missing_fields"]
    assert data["where_used_count"] >= 1


def test_datasheet_url_counts_as_present_in_parts_list_and_insights(client, user):
    role = Role(name="datasheet_viewer", permissions=[
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
        ]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    part = Part(
        part_number="HW-URL",
        revision="A",
        description="Purchased component",
        processes=["hardware"],
        attrs={
            "material": "Steel",
            "datasheet": "https://example.com/file.pdf",
            "approvedby": "QA Person",
        },
    ).save()

    list_resp = client.post("/api/parts_lazy", json={"first": 0, "rows": 25, "filters": {}})
    assert list_resp.status_code == 200
    rows = list_resp.get_json()["data"]
    row = next(item for item in rows if item["part_number"] == part.part_number and item["revision"] == part.revision)
    assert row["has_datasheet"] is True

    insights_resp = client.get(f"/api/parts/{part.part_number}/insights?rev={part.revision}")
    assert insights_resp.status_code == 200
    data = insights_resp.get_json()
    assert data["deliverables_present"]["datasheet"] is True
    assert "datasheet" not in (data.get("deliverables_missing_recommended") or [])
