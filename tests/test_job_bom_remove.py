from app.models.auth import Role
from app.models.job import Job, JobBOMLine
from app.models.part import Part


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def test_job_bom_remove_uses_line_rev(client, user):
    role = Role(name="admin").save()
    user.roles = [role]
    user.save()
    _login(client, user)

    Part(part_number="PN-1", revision="A", description="Test").save()
    job = Job(job_number="JOB-100", title="Test Job").save()
    job.bom = [JobBOMLine(pn="PN-1", rev="", qty=2)]
    job.save()

    resp = client.get(f"/admin/jobs/{job.id}/bom_json")
    assert resp.status_code == 200
    rows = resp.get_json()
    assert rows and rows[0]["rev"] == ""
    assert rows[0]["line_rev"] == ""

    resp2 = client.post(
        f"/admin/jobs/{job.id}/bom_remove",
        json={"pn": "PN-1", "line_rev": ""},
    )
    assert resp2.status_code == 200
    job.reload()
    assert len(job.bom) == 0
