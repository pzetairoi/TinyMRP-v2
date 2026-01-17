from app.models.auth import Role
from app.models.part import Part
from app.models.bom import BOMLink
from app.models.artifact import PartFile


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def test_part_insights_shape(client, user):
    role = Role(name="viewer", permissions=["items.view"]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    part = Part(part_number="HW-55", revision="", description="Washer", processes=["hardware"], attrs={"material": "Steel"}).save()
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
