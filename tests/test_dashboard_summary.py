from app.models.auth import Role
from app.models.part import Part
from app.models.bom import BOMLink
from app.models.artifact import PartFile


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def test_dashboard_summary_shape(client, user):
    role = Role(name="viewer", permissions=["items.view"]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    root = Part(part_number="ASM-300", revision="", description="Root").save()
    child = Part(part_number="HW-30", revision="", description="Bolt", processes=["hardware"]).save()
    BOMLink(parent_pn=root.part_number, parent_rev="", child_pn=child.part_number, child_rev="", qty=5).save()
    PartFile(
        part_number=child.part_number,
        revision="",
        ext_group="pdf",
        ext="pdf",
        rel_path="HW-30.pdf",
        path="C:/tmp/HW-30.pdf",
    ).save()

    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "counts" in data
    assert "doc_coverage" in data
    assert "data_health" in data
    assert "top_processes" in data
    assert "recent_parts" in data
    assert "top_hardware" in data


def test_dashboard_summary_excludes_placeholder_approval_values(client, user):
    role = Role(name="viewer", permissions=["items.view"]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    Part(part_number="APR-REAL", revision="A", description="Approved", attrs={"approvedby": "QA"}).save()
    Part(part_number="APR-RAW", revision="A", description="Placeholder raw", attrs={"approved": "Approved"}).save()
    Part(
        part_number="APR-CANON",
        revision="A",
        description="Placeholder canonical",
        canonical={"approved_by": "Approved By"},
    ).save()

    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["counts"]["approved"] == 1
