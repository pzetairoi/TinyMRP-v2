import uuid

from app.models.auth import Role, User
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.job import Job
from app.models.order import Order, OrderLine
from app.services.api_tokens import create_token
from app.services.acl import allowed_parts_for


def _role(name: str, perms: list[str]) -> Role:
    r = Role(name=name, permissions=perms)
    r.save()
    return r


def _user(email: str, role: Role) -> User:
    u = User(
        email=email,
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=[role],
    )
    u.save()
    return u


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_customer_viewer_scoping_api(client, app):
    with app.app_context():
        role = _role("viewer", [
            "jobs.read",
            "orders.read",
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
        ])
        user = _user("cust.viewer@example.com", role)
        cust1 = Customer(name="Cust A", users=[user]).save()
        cust2 = Customer(name="Cust B").save()

        job1 = Job(job_number="JOB-1", customer=cust1).save()
        job2 = Job(job_number="JOB-2", customer=cust2).save()

        order1 = Order(order_number="SO-1", kind="sales", job=job1).save()
        order2 = Order(order_number="PO-2", job=job2, customer=cust2).save()
        order3 = Order(order_number="SO-3", kind="sales", customer=cust1).save()

        _, token = create_token(user, "cust")

    r = client.get("/api/jobs", headers=_auth_headers(token))
    assert r.status_code == 200
    items = [i["job_number"] for i in r.json["items"]]
    assert "JOB-1" in items
    assert "JOB-2" not in items

    r = client.get("/api/jobs/JOB-2", headers=_auth_headers(token))
    assert r.status_code == 404

    r = client.get("/api/orders", headers=_auth_headers(token))
    assert r.status_code == 200
    orders = [i["order_number"] for i in r.json["items"]]
    assert "SO-1" in orders
    assert "SO-3" in orders
    assert "PO-2" not in orders

    with app.app_context():
        allowed = allowed_parts_for(user)
        assert allowed is not None


def test_supplier_viewer_scoping_api(client, app):
    with app.app_context():
        role = _role("viewer", [
            "jobs.read",
            "orders.read",
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
        ])
        user = _user("supp.viewer@example.com", role)
        supp1 = Supplier(name="Supp A", users=[user]).save()
        supp2 = Supplier(name="Supp B").save()

        job1 = Job(job_number="JOB-10", vendors=[supp1]).save()
        job2 = Job(job_number="JOB-20", vendors=[supp2]).save()

        order1 = Order(order_number="PO-10", supplier=supp1, job=job2).save()
        order2 = Order(order_number="PO-20", supplier=supp2, job=job1).save()

        _, token = create_token(user, "supp")

    r = client.get("/api/orders", headers=_auth_headers(token))
    assert r.status_code == 200
    orders = [i["order_number"] for i in r.json["items"]]
    assert "PO-10" in orders
    assert "PO-20" not in orders

    r = client.get("/api/jobs", headers=_auth_headers(token))
    assert r.status_code == 200
    jobs = [i["job_number"] for i in r.json["items"]]
    assert jobs == ["JOB-10", "JOB-20"]

    r = client.get("/api/jobs/JOB-10", headers=_auth_headers(token))
    assert r.status_code == 200


def test_internal_role_unscoped(client, app):
    with app.app_context():
        role = _role("planner", [
            "jobs.read",
            "orders.read",
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
        ])
        user = _user("planner@example.com", role)
        cust = Customer(name="Cust Z").save()
        supp = Supplier(name="Supp Z").save()
        Job(job_number="JOB-X", customer=cust).save()
        Job(job_number="JOB-Y").save()
        Order(order_number="PO-X", supplier=supp).save()
        Order(order_number="PO-Y").save()
        _, token = create_token(user, "planner")

    r = client.get("/api/jobs", headers=_auth_headers(token))
    assert r.status_code == 200
    jobs = {i["job_number"] for i in r.json["items"]}
    assert "JOB-X" in jobs
    assert "JOB-Y" in jobs

    r = client.get("/api/orders", headers=_auth_headers(token))
    assert r.status_code == 200
    orders = {i["order_number"] for i in r.json["items"]}
    assert "PO-X" in orders
    assert "PO-Y" in orders
