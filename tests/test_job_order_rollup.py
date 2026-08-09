from app.models.auth import Role
from app.models.part import Part
from app.models.bom import BOMLink
from app.models.job import Job, JobBOMLine
from app.models.order import Order, OrderLine
from app.views.admin_jobs import _build_job_bom_rollup
from app.services.permissions import PERMISSION_REGISTRY


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _seed_three_level_bom():
    Part(part_number="ASM-A", revision="A", description="Top assembly").save()
    Part(part_number="SUB-B", revision="A", description="Intermediate assembly").save()
    Part(part_number="PART-C", revision="A", description="Child part").save()
    BOMLink(parent_pn="ASM-A", parent_rev="A", child_pn="SUB-B", child_rev="A", qty=2).save()
    BOMLink(parent_pn="SUB-B", parent_rev="A", child_pn="PART-C", child_rev="A", qty=3).save()


def test_rollup_expands_orders_and_flags_overordered_children(app):
    _seed_three_level_bom()
    job = Job(job_number="JOB-ROLLUP-1", title="Rollup Test").save()
    job.bom = [JobBOMLine(pn="ASM-A", rev="A", qty=1)]
    job.save()

    Order(
        order_number="PO-CHILD",
        job=job,
        status="confirmed",
        lines=[OrderLine(pn="SUB-B", rev="A", qty=1)],
    ).save()
    Order(
        order_number="PO-PARENT",
        job=job,
        status="confirmed",
        lines=[OrderLine(pn="ASM-A", rev="A", qty=1)],
    ).save()

    with app.test_request_context():
        rollup = _build_job_bom_rollup(job, can_manage_orders=True)

    flat = {row["pn"]: row for row in rollup["flat_rows"]}
    assert flat["ASM-A"]["required"] == 1.0
    assert flat["ASM-A"]["ordered"] == 1.0
    assert flat["ASM-A"]["remaining"] == 0.0

    assert flat["SUB-B"]["required"] == 2.0
    assert flat["SUB-B"]["ordered"] == 3.0
    assert flat["SUB-B"]["over"] == 1.0

    assert flat["PART-C"]["required"] == 6.0
    assert flat["PART-C"]["ordered"] == 9.0
    assert flat["PART-C"]["over"] == 3.0

    over = {row["pn"] for row in rollup["oversupplied_parts"]}
    assert "SUB-B" in over
    assert "PART-C" in over

    remaining = {row["pn"] for row in rollup["remaining_parts_flat"]}
    assert "SUB-B" not in remaining
    assert "PART-C" not in remaining

    child_orders = {o["order_number"] for o in flat["PART-C"]["orders"]}
    assert child_orders == {"PO-CHILD", "PO-PARENT"}


def test_jobs_edit_shows_flat_tree_toggle_and_tree_levels(client, user):
    role = Role(name="administrator", permissions=sorted(PERMISSION_REGISTRY)).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    _seed_three_level_bom()
    job = Job(job_number="JOB-ROLLUP-2", title="Tree Toggle Test").save()
    job.bom = [JobBOMLine(pn="ASM-A", rev="A", qty=1)]
    job.save()

    Order(
        order_number="PO-PARTIAL",
        job=job,
        status="confirmed",
        lines=[OrderLine(pn="SUB-B", rev="A", qty=1)],
    ).save()

    resp = client.get(f"/admin/jobs/{job.id}/edit")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="remaining-view-flat"' in html
    assert 'id="remaining-view-tree"' in html
    assert 'id="remaining-tree-wrap"' in html
    assert 'data-level="+.01"' in html
    assert 'data-level="+.01.01"' in html
