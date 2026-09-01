"""Progressive ordering across a multi-level job BOM.

Help "Workflow B: Progressive Ordering Across Multi-Level BOM" promises that a
job's roots expand into the full multi-level BOM, that purchasing can select
top-level assemblies, intermediate subassemblies or leaf components, and that
each non-draft purchase order updates coverage until remaining demand is zero.
These tests hold the job detail page and the create-order-from-job endpoint to
that promise for every role allowed to run it.
"""

import re
import uuid

import pytest

from app.models.auth import Role, User
from app.models.bom import BOMLink
from app.models.customer import Customer
from app.models.job import Job, JobBOMLine
from app.models.order import Order, OrderLine
from app.models.part import Part
from app.services.standard_roles import STANDARD_ROLES

ROW = re.compile(
    r'<tr class="remaining-row" data-pn="(?P<pn>[^"]*)"[^>]*?'
    r'data-rev="(?P<rev>[^"]*)" data-level="(?P<level>[^"]*)" '
    r'data-remaining="(?P<remaining>[^"]*)"'
)
ORDER_BUTTON = 'data-act="submit-remaining-order"'

# Roles the help lists as running the order workflow.
ORDERING_ROLES = ("administrator", "commercial")
# Roles that read jobs but must not create orders. engineering_manager,
# engineering and auditor have no jobs.update, so they only ever reach the
# read-only job detail page - the page this regression emptied.
READ_ONLY_ROLES = ("engineering_manager", "engineering", "internal", "workshop", "auditor")


def _role(name):
    existing = Role.objects(name=name).first()
    if existing:
        return existing
    return Role(name=name, permissions=list(STANDARD_ROLES[name].permissions)).save()


def _user(email, role_name):
    return User(
        email=email,
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=[_role(role_name)],
    ).save()


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = user.get_id()
        session["_fresh"] = True


def _part(pn, rev, *, approved=True):
    return Part(
        part_number=pn,
        revision=rev,
        description=f"{pn} description",
        attrs={"approved": bool(approved)},
    ).save()


def _hold(pn):
    """Take a part back to unreleased through the resolver that owns the flag."""

    part = Part.objects(part_number=pn).first()
    part.attrs = {"approved": False}
    part.save()


def _seed_tree():
    """Two job roots that share one leaf, so consolidation is observable.

    ASM-A x1  -> SUB-B x2 -> BOLT-D x3      (6 BOLT-D)
              -> BOLT-D x1                  (1 BOLT-D)
    ASM-E x2  -> BOLT-D x5                  (10 BOLT-D)
    """

    for pn in ("ASM-A", "SUB-B", "BOLT-D", "ASM-E", "OUTSIDE-Z"):
        _part(pn, "A")
    BOMLink(parent_pn="ASM-A", parent_rev="A", child_pn="SUB-B", child_rev="A", qty=2).save()
    BOMLink(parent_pn="ASM-A", parent_rev="A", child_pn="BOLT-D", child_rev="A", qty=1).save()
    BOMLink(parent_pn="SUB-B", parent_rev="A", child_pn="BOLT-D", child_rev="A", qty=3).save()
    BOMLink(parent_pn="ASM-E", parent_rev="A", child_pn="BOLT-D", child_rev="A", qty=5).save()


def _job(number="JOB-PARTIAL", customer=None):
    job = Job(job_number=number, title="Partial ordering", customer=customer).save()
    job.bom = [
        JobBOMLine(pn="ASM-A", rev="A", qty=1),
        JobBOMLine(pn="ASM-E", rev="A", qty=2),
    ]
    job.save()
    return job


def _rows(html, *, view):
    """Remaining rows from one view. Tree rows carry a BOM level, flat rows do not."""

    out = {}
    for match in ROW.finditer(html):
        is_tree = bool(match.group("level"))
        if is_tree != (view == "tree"):
            continue
        remaining = float(match.group("remaining"))
        if view == "tree":
            out.setdefault(match.group("pn"), []).append(
                (match.group("level"), remaining)
            )
        else:
            out[match.group("pn")] = remaining
    return out


def _order_from_job(client, job, parts):
    import json

    return client.post(
        f"/admin/orders/from_job/{job.id}",
        data={"parts_json": json.dumps(parts)},
        follow_redirects=False,
    )


def _confirm(order_number):
    order = Order.objects(order_number=order_number).first()
    order.status = "submitted"
    order.save()
    return order


# --- the regression: every BOM level reaches the page ------------------------


@pytest.mark.parametrize("role_name", ORDERING_ROLES)
def test_job_detail_offers_every_bom_level_to_each_ordering_role(client, role_name):
    _seed_tree()
    job = _job()
    _login(client, _user(f"{role_name}@ordering.test", role_name))

    response = client.get(f"/admin/jobs/{job.id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    # Top-level assemblies, intermediate subassemblies and leaf components, as
    # the help promises - not just the two parts assigned to the job.
    assert set(_rows(html, view="flat")) == {"ASM-A", "SUB-B", "BOLT-D", "ASM-E"}
    assert ORDER_BUTTON in html


@pytest.mark.parametrize("role_name", ORDERING_ROLES)
def test_read_only_and_editable_job_pages_agree(client, role_name):
    _seed_tree()
    job = _job()
    _login(client, _user(f"{role_name}@agree.test", role_name))

    view = _rows(client.get(f"/admin/jobs/{job.id}").get_data(as_text=True), view="flat")
    edit = _rows(
        client.get(f"/admin/jobs/{job.id}/edit").get_data(as_text=True), view="flat"
    )
    assert view == edit


@pytest.mark.parametrize("role_name", READ_ONLY_ROLES)
def test_read_only_roles_see_the_whole_tree_without_the_order_button(client, role_name):
    _seed_tree()
    job = _job()
    _login(client, _user(f"{role_name}@readonly.test", role_name))

    html = client.get(f"/admin/jobs/{job.id}").get_data(as_text=True)
    assert set(_rows(html, view="flat")) == {"ASM-A", "SUB-B", "BOLT-D", "ASM-E"}
    assert ORDER_BUTTON not in html


def test_shared_child_is_consolidated_flat_and_itemised_in_tree(client):
    _seed_tree()
    job = _job()
    _login(client, _user("consolidate@ordering.test", "commercial"))
    html = client.get(f"/admin/jobs/{job.id}").get_data(as_text=True)

    # 1x2x3 under ASM-A, 1x1 direct under ASM-A, 2x5 under ASM-E.
    assert _rows(html, view="flat")["BOLT-D"] == 17.0
    tree = _rows(html, view="tree")
    assert sorted(qty for _level, qty in tree["BOLT-D"]) == [1.0, 6.0, 10.0]
    # Every occurrence carries its BOM level path, so purchasing can see which
    # parent each quantity came from before consolidating the buy.
    assert all(level for level, _qty in tree["BOLT-D"])


# --- ordering at any level, progressively ------------------------------------


@pytest.mark.parametrize("role_name", ORDERING_ROLES)
def test_one_order_can_mix_root_intermediate_and_leaf_parts(client, role_name):
    _seed_tree()
    job = _job()
    _login(client, _user(f"{role_name}@mixed.test", role_name))

    response = _order_from_job(
        client,
        job,
        [
            {"pn": "ASM-A", "rev": "A", "qty": 1},
            {"pn": "SUB-B", "rev": "A", "qty": 2},
            {"pn": "BOLT-D", "rev": "A", "qty": 17},
        ],
    )
    assert response.status_code == 302

    order = Order.objects(job=job).first()
    assert order.kind == "purchase"
    assert order.status == "draft"
    assert {(line.pn, line.qty) for line in order.lines} == {
        ("ASM-A", 1.0),
        ("SUB-B", 2.0),
        ("BOLT-D", 17.0),
    }


def test_partial_order_leaves_the_rest_orderable(client):
    _seed_tree()
    job = _job()
    _login(client, _user("partial@ordering.test", "commercial"))

    _order_from_job(client, job, [{"pn": "BOLT-D", "rev": "A", "qty": 6}])
    order = Order.objects(job=job).first()

    # Help: draft orders are excluded from coverage.
    html = client.get(f"/admin/jobs/{job.id}").get_data(as_text=True)
    assert _rows(html, view="flat")["BOLT-D"] == 17.0

    _confirm(order.order_number)
    html = client.get(f"/admin/jobs/{job.id}").get_data(as_text=True)
    assert _rows(html, view="flat")["BOLT-D"] == 11.0

    # The rest is still selectable, which is the whole point of partial buying.
    _order_from_job(client, job, [{"pn": "BOLT-D", "rev": "A", "qty": 11}])
    second = Order.objects(job=job, order_number__ne=order.order_number).first()
    _confirm(second.order_number)

    html = client.get(f"/admin/jobs/{job.id}").get_data(as_text=True)
    assert "BOLT-D" not in _rows(html, view="flat")
    assert set(_rows(html, view="flat")) == {"ASM-A", "SUB-B", "ASM-E"}


def test_buying_a_parent_covers_its_children(client):
    _seed_tree()
    job = _job()
    _login(client, _user("parent@ordering.test", "commercial"))

    _order_from_job(client, job, [{"pn": "SUB-B", "rev": "A", "qty": 2}])
    _confirm(Order.objects(job=job).first().order_number)

    flat = _rows(
        client.get(f"/admin/jobs/{job.id}").get_data(as_text=True), view="flat"
    )
    assert "SUB-B" not in flat
    # 2 x SUB-B carries 6 BOLT-D with it, so only the other 11 remain to buy.
    assert flat["BOLT-D"] == 11.0


def test_sales_order_for_the_job_product_is_not_procurement_coverage(client):
    _seed_tree()
    job = _job()
    _login(client, _user("sales@ordering.test", "commercial"))

    # The customer order the job exists to fulfil is demand, not supply. Before
    # this was separated it marked the whole exploded tree as bought.
    Order(
        order_number="SO-JOB",
        kind="sales",
        job=job,
        status="in_production",
        lines=[OrderLine(pn="ASM-A", rev="A", qty=1), OrderLine(pn="ASM-E", rev="A", qty=2)],
    ).save()

    flat = _rows(
        client.get(f"/admin/jobs/{job.id}").get_data(as_text=True), view="flat"
    )
    assert flat == {"ASM-A": 1.0, "SUB-B": 2.0, "BOLT-D": 17.0, "ASM-E": 2.0}


def test_cancelled_purchase_order_does_not_cover(client):
    _seed_tree()
    job = _job()
    _login(client, _user("cancelled@ordering.test", "commercial"))

    Order(
        order_number="PO-CANCELLED",
        kind="purchase",
        job=job,
        status="cancelled",
        lines=[OrderLine(pn="BOLT-D", rev="A", qty=17)],
    ).save()

    flat = _rows(
        client.get(f"/admin/jobs/{job.id}").get_data(as_text=True), view="flat"
    )
    assert flat["BOLT-D"] == 17.0


# --- authorisation of the posted selection -----------------------------------


def test_part_outside_the_job_tree_is_rejected(client):
    _seed_tree()
    job = _job()
    _login(client, _user("outside@ordering.test", "commercial"))

    response = _order_from_job(client, job, [{"pn": "OUTSIDE-Z", "rev": "A", "qty": 1}])
    assert response.status_code == 404
    assert Order.objects(job=job).count() == 0


def test_a_rejected_part_does_not_leak_the_rest_of_the_selection(client):
    _seed_tree()
    job = _job()
    _login(client, _user("mixedreject@ordering.test", "commercial"))

    response = _order_from_job(
        client,
        job,
        [{"pn": "BOLT-D", "rev": "A", "qty": 1}, {"pn": "OUTSIDE-Z", "rev": "A", "qty": 1}],
    )
    assert response.status_code == 404
    assert Order.objects(job=job).count() == 0


def test_unreleased_child_is_neither_listed_nor_orderable_without_permission(client):
    _seed_tree()
    _hold("SUB-B")
    job = _job()

    # Commercial has no parts.read_unreleased, so the held subassembly and the
    # descendants it gates stop the walk.
    _login(client, _user("held@ordering.test", "commercial"))
    flat = _rows(
        client.get(f"/admin/jobs/{job.id}").get_data(as_text=True), view="flat"
    )
    assert "SUB-B" not in flat
    assert _order_from_job(client, job, [{"pn": "SUB-B", "rev": "A", "qty": 1}]).status_code == 404
    assert Order.objects(job=job).count() == 0


def test_administrator_still_sees_and_orders_the_unreleased_child(client):
    _seed_tree()
    _hold("SUB-B")
    job = _job()

    _login(client, _user("heldadmin@ordering.test", "administrator"))
    flat = _rows(
        client.get(f"/admin/jobs/{job.id}").get_data(as_text=True), view="flat"
    )
    assert flat["SUB-B"] == 2.0
    assert _order_from_job(client, job, [{"pn": "SUB-B", "rev": "A", "qty": 2}]).status_code == 302


@pytest.mark.parametrize("role_name", READ_ONLY_ROLES)
def test_roles_without_orders_create_cannot_post(client, role_name):
    _seed_tree()
    job = _job()
    _login(client, _user(f"{role_name}@nocreate.test", role_name))

    response = _order_from_job(client, job, [{"pn": "BOLT-D", "rev": "A", "qty": 1}])
    assert response.status_code == 403
    assert Order.objects(job=job).count() == 0


def test_customer_portal_reads_its_job_scope_but_cannot_order(client):
    _seed_tree()
    customer = Customer(code="C-PARTIAL", name="Portal Customer").save()
    job = _job(customer=customer)
    portal = _user("portal@ordering.test", "customer")
    customer.users = [portal]
    customer.save()
    _login(client, portal)

    html = client.get(f"/admin/jobs/{job.id}").get_data(as_text=True)
    assert set(_rows(html, view="flat")) == {"ASM-A", "SUB-B", "BOLT-D", "ASM-E"}
    assert ORDER_BUTTON not in html
    assert _order_from_job(client, job, [{"pn": "BOLT-D", "rev": "A", "qty": 1}]).status_code == 403
    assert Order.objects(job=job).count() == 0


# --- the shipped help must describe what the code above actually does --------


def _help_html():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    return (root / "app" / "static" / "help" / "help.html").read_text(encoding="utf-8")


def _job_form_template():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    return (
        root / "app" / "templates" / "admin" / "jobs_form.html"
    ).read_text(encoding="utf-8")


def test_help_names_the_button_the_job_page_actually_renders():
    # Workflow B step 4 tells the reader what to click. The label drifted once
    # already; a reader following the help must find that exact control.
    assert "Create purchase order from selected" in _job_form_template()
    assert "Create purchase order from selected" in _help_html()


def test_help_states_that_only_purchase_orders_cover_a_job():
    help_html = _help_html()
    assert "Only purchase orders cover a job" in help_html
    assert "never counted as parts already bought" in help_html
    assert "Each new non-draft purchase order updates coverage" in help_html


def test_help_still_promises_ordering_at_every_bom_level():
    help_html = _help_html()
    for promise in (
        "Top-level assemblies",
        "Intermediate subassemblies",
        "Leaf components",
    ):
        assert promise in help_html

def test_help_documents_the_controls_the_job_page_renders():
    """Workflow B names five filters and a select-all; all six must exist."""

    template = _job_form_template()
    for control in (
        "remaining-filter-pn",
        "remaining-filter-desc",
        "remaining-filter-rev",
        "remaining-filter-level",
        "remaining-filter-qty-min",
        "remaining-select-all",
    ):
        assert control in template, control
    # The help promises the selection survives a filter change but is cleared
    # by the Flat/Tree toggle. Only setRemainingView may clear the boxes.
    view_toggle = template.split("function setRemainingView")[1].split("function ")[0]
    assert "remaining-select" in view_toggle and "checked = false" in view_toggle
    apply_filters = template.split("function applyRemainingFilters")[1].split("function ")[0]
    assert "input.remaining-select-all" in apply_filters
    assert "input.remaining-select'" not in apply_filters


def test_help_worked_example_matches_the_rollup_it_describes(client):
    """The numbers printed in Workflow B are the numbers the code produces."""

    _login(client, _user("worked-example@ordering.test", "administrator"))

    # Two roots, one nested inside the other, exactly as the help's table says.
    for pn in ("TRAILER", "FRAME", "PLATE"):
        _part(pn, "A")
    BOMLink(parent_pn="TRAILER", parent_rev="A", child_pn="FRAME", child_rev="A", qty=1).save()
    BOMLink(parent_pn="FRAME", parent_rev="A", child_pn="PLATE", child_rev="A", qty=2).save()
    job = Job(job_number="JOB-WORKED", title="Worked example").save()
    job.bom = [JobBOMLine(pn="TRAILER", rev="A", qty=2), JobBOMLine(pn="FRAME", rev="A", qty=1)]
    job.save()

    html = client.get(f"/admin/jobs/{job.id}").get_data(as_text=True)
    flat = _rows(html, view="flat")
    tree = _rows(html, view="tree")

    # "two trailers each containing one core frame, plus one spare frame, makes
    # CV03-F01 required three times"
    assert flat["FRAME"] == 3.0
    # "each JOIN PLATE inside that frame (two per frame) is required six times"
    assert flat["PLATE"] == 6.0
    # "+.01 is the first job root, +.02 the second, and each further segment
    # steps down one BOM level"
    levels = dict(sorted(tree["PLATE"]))
    assert levels == {"+.01.01.01": 4.0, "+.02.01": 2.0}
    # Tree occurrences add up to the flat line the buyer orders from.
    assert sum(levels.values()) == flat["PLATE"]
