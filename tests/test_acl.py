import uuid

from app.models.auth import Role, User
from app.models.part import Part
from app.models.bom import BOMLink
from app.models.job import Job, JobBOMLine
from app.models.order import Order, OrderLine
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.services.acl import allowed_parts_for, part_is_allowed


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


def test_customer_viewer_allowed_parts(app):
    with app.app_context():
        role = Role(name="customer_viewer").save()
        user = _user("cust@example.com", role)
        cust = Customer(name="Customer A", users=[user]).save()

        Part(part_number="ASM-1001", revision="A", description="Root").save()
        Part(part_number="CMP-2002", revision="A", description="Child").save()
        BOMLink(parent_pn="ASM-1001", parent_rev="A", child_pn="CMP-2002", child_rev="A", qty=2).save()

        Job(job_number="JOB-1", customer=cust, bom=[JobBOMLine(pn="ASM-1001", rev="A", qty=1)]).save()

        allowed = allowed_parts_for(user)
        assert allowed is not None
        assert part_is_allowed(allowed, "ASM-1001", "A")
        assert part_is_allowed(allowed, "CMP-2002", "A")
        assert not part_is_allowed(allowed, "NOPE-1", "A")


def test_supplier_viewer_allowed_parts(app):
    with app.app_context():
        role = Role(name="supplier_viewer").save()
        user = _user("supp@example.com", role)
        supp = Supplier(name="Supplier A", users=[user]).save()

        Part(part_number="CMP-3000", revision="B", description="Ordered").save()
        Part(part_number="MAT-9999", revision="A", description="Child").save()
        BOMLink(parent_pn="CMP-3000", parent_rev="B", child_pn="MAT-9999", child_rev="A", qty=1).save()

        Order(
            order_number="PO-1",
            supplier=supp,
            lines=[OrderLine(pn="CMP-3000", rev="B", qty=3, uom="EA")],
        ).save()

        allowed = allowed_parts_for(user)
        assert allowed is not None
        assert part_is_allowed(allowed, "CMP-3000", "B")
        assert not part_is_allowed(allowed, "CMP-3000", "")
        assert part_is_allowed(allowed, "MAT-9999", "A")
        assert not part_is_allowed(allowed, "NOPE-2", "A")
