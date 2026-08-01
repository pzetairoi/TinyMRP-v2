"""Guards for the per-request caches added for parts/BOM performance.

Each cache must stay invisible to callers: scoping, permissions and the
configured approval aliases have to behave exactly as they did without it.
"""
import uuid

from app.models.auth import Role, User
from app.models.bom import BOMLink
from app.models.customer import Customer
from app.models.job import Job, JobBOMLine
from app.models.part import Part
from app.services.standard_roles import STANDARD_ROLES


def _role(name, permissions):
    return Role(name=name, permissions=list(permissions)).save()


def _standard_role(name):
    existing = Role.objects(name=name).first()
    if existing:
        return existing
    return _role(name, STANDARD_ROLES[name].permissions)


def _user(email, *roles):
    return User(
        email=email, password="test", active=True,
        fs_uniquifier=str(uuid.uuid4()), roles=list(roles),
    ).save()


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = user.get_id()
        session["_fresh"] = True


def test_scoped_revision_cache_is_keyed_per_user(app):
    """Two users in one request context must not share a resolved revision.

    The lookup is scope-filtered, so a cache keyed only on the part number
    would hand one user another user's visible revision.
    """
    from app.views.bom_tree import _resolve_scoped_revision

    Part(part_number="CACHE-REV", revision="A", description="A",
         attrs={"approvedby": "QA"}).save()
    engineer = _user("cache-eng@t.test", _standard_role("engineering"))
    portal = _user("cache-portal@t.test", _standard_role("customer"))

    with app.test_request_context("/"):
        first = _resolve_scoped_revision("CACHE-REV", "", engineer)
        second = _resolve_scoped_revision("CACHE-REV", "", portal)
        # Each identity is resolved independently rather than reusing the
        # first answer, and a repeat for the same user stays consistent.
        assert _resolve_scoped_revision("CACHE-REV", "", engineer) == first
        assert _resolve_scoped_revision("CACHE-REV", "", portal) == second

        cache = __import__("flask").g._bom_scoped_revision_cache
        assert {key[1] for key in cache} == {str(engineer.id), str(portal.id)}

    # An explicit revision never consults the cache at all.
    with app.test_request_context("/"):
        assert _resolve_scoped_revision("CACHE-REV", "B", engineer) == "B"


def test_annotation_preload_still_honours_comment_permissions(client):
    """Preloading documents must not expose notes to roles that cannot read."""
    Part(part_number="CACHE-NOTE", revision="A", description="N",
         attrs={"approvedby": "QA"}).save()

    portal = _user("cache-note-portal@t.test", _standard_role("customer"))
    customer = Customer(name="Note Customer", users=[portal]).save()
    Job(job_number="NOTE-JOB", customer=customer,
        bom=[JobBOMLine(pn="CACHE-NOTE", rev="A", qty=1)]).save()
    _login(client, portal)

    response = client.post("/api/parts_lazy", json={"first": 0, "rows": 25})
    assert response.status_code == 200
    for row in response.get_json().get("rows", []):
        assert not row.get("comments")
        assert not row.get("notes")


def test_approval_alias_still_resolves_after_index_refactor(app):
    """The canonical index must honour configured aliases, not just 'approved'."""
    from app.services.canonical_fields import resolve_approval

    with app.app_context():
        # Alias spelling, odd casing and separators all fold to the same field.
        for key in ("approvedby", "Approved By", "APPROVED_BY", "approved-by"):
            result = resolve_approval({key: "QA Person"})
            assert result["approved"] is True, key
            assert result["approved_by"] == "QA Person", key

        # A blankish alias value must not read as approved.
        assert resolve_approval({"approvedby": ""})["approved"] is False
        assert resolve_approval({})["approved"] is False


def test_part_detail_survives_order_referencing_deleted_job(client):
    """A deleted job must not break the part page it is unrelated to.

    Deleting a Job leaves the referencing Order's DBRef dangling; mongoengine
    raises on access, which previously failed the whole part_detail response
    and made the UI report missing comments/markups permissions.
    """
    from app.models.order import Order, OrderLine

    Part(part_number="DANGLE-1", revision="A", description="D",
         attrs={"approvedby": "QA"}).save()
    job = Job(job_number="DANGLE-JOB").save()
    Order(order_number="PO-DANGLE", kind="purchase", job=job,
          lines=[OrderLine(pn="DANGLE-1", rev="A", qty=1)]).save()
    # Drop the job, leaving the order pointing at a missing document.
    job.delete()

    admin = _user("dangle-admin@t.test", _standard_role("administrator"))
    _login(client, admin)

    response = client.get("/api/part_detail?pn=DANGLE-1&rev=A")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["can_comments_read"] is True
    assert payload["can_markups_read"] is True


def test_deleting_a_job_nullifies_referencing_orders():
    """Hard-deleting a Job must not leave orders pointing at a missing doc."""
    from app.models.order import Order

    job = Job(job_number="NULLIFY-JOB").save()
    order = Order(order_number="PO-NULLIFY", kind="purchase", job=job).save()

    job.delete()

    order.reload()
    assert order.job is None
