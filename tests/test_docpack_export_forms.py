import io
import os
import uuid
import zipfile

from reportlab.pdfgen import canvas

from app.models.auth import Role, User
from app.models.customer import Customer
from app.models.job import Job, JobBOMLine
from app.models.order import Order, OrderLine
from app.models.part import Part
from app.models.artifact import PartFile


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _make_user(email: str, permissions=None):
    role = Role(name=f"role-{uuid.uuid4()}", permissions=permissions or []).save()
    return User(
        email=email,
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=[role],
    ).save()


def _write_pdf(path: str, label: str) -> None:
    c = canvas.Canvas(path)
    c.drawString(100, 750, label)
    c.showPage()
    c.save()


def test_jobs_form_docpack_section_keeps_field_names_and_hooks(client, app):
    """The job export form was restyled to match the Excel Compile builder;
    this locks in that every field name the backend actually reads survived
    the restyle, plus the JS hook classes the new progress bar/binder-toggle
    script depends on.
    """
    user = _make_user(
        "jobs-form@example.com",
        [
            "jobs.read",
            "exports.run",
            "parts.read",
            "bom.read",
            "files.read",
            "markups.read",
        ],
    )
    job = Job(job_number="JOB-FORM-1", title="Sample job").save()

    _login(client, user)
    resp = client.get(f"/admin/jobs/{job.id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert "Docpack export" in body
    assert 'class="docpack-export-form" data-prefix="job"' in body
    assert "docpack-progress-wrap" in body
    assert "job-binder-toggle" in body
    assert "job-binder-options" in body

    for name in [
        "depth", "classified", "process_mode", "output_name", "processes", "file_types",
        "selected_files", "excel_bom", "pdf_binder", "index_pdf", "visual_list",
        "hardware_summary", "cover_page", "whereused_report", "fabrication_pack",
        "markup_files", "markup_report",
        "excel_all_fields", "include_consumed",
        "binder_add_cover", "binder_add_index", "binder_add_visual_list",
        "binder_add_whereused", "binder_add_datasheets", "binder_add_hardware_summary",
        "binder_page_numbers", "binder_include_flat_patterns",
        "binder_add_markups",
        "stamp_quote", "stamp_confidential", "stamp_approved", "stamp_wip", "stamp_inprogress",
    ]:
        assert f'name="{name}"' in body, f"missing field: {name}"


def test_orders_form_docpack_and_scope_sections_keep_field_names(client, app):
    user = _make_user(
        "orders-form@example.com",
        [
            "orders.read",
            "exports.run",
            "parts.read",
            "bom.read",
            "files.read",
            "markups.read",
        ],
    )
    customer = Customer(name="Acme").save()
    order = Order(order_number="ORD-FORM-1", customer=customer, status="submitted", kind="sales").save()

    _login(client, user)
    resp = client.get(f"/admin/orders/{order.id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert "Docpack export" in body
    assert "Scope of supply" in body
    assert 'data-prefix="order"' in body
    assert 'data-prefix="scope"' in body

    for name in [
        "depth", "classified", "process_mode", "output_name", "processes", "file_types",
        "selected_files", "excel_bom", "pdf_binder", "binder_add_datasheets",
        "markup_files", "markup_report", "binder_add_markups",
        "stamp_quote", "stamp_inprogress",
    ]:
        assert f'name="{name}"' in body, f"missing docpack field: {name}"

    for name in ["attach_docs", "include_children", "include_binder", "file_types"]:
        assert f'name="{name}"' in body, f"missing scope-of-supply field: {name}"


def test_build_job_docpack_endpoint_end_to_end(app, client, tmp_path):
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    user = _make_user(
        "jobs-build@example.com",
        [
            "jobs.view",
            "items.view",
            "exports.run",
            "parts.read_unreleased",
        ],
    )
    part = Part(part_number="JOB-PN-1", revision="1", description="Job Part", processes=["machine"]).save()
    pdf_path = os.path.join(root_dir, "JOB-PN-1.pdf")
    _write_pdf(pdf_path, "JOB PART PDF")
    PartFile(part_number=part.part_number, revision="1", ext_group="pdf", ext="pdf",
              rel_path="JOB-PN-1.pdf", path=pdf_path).save()

    job = Job(job_number="JOB-BUILD-1", bom=[JobBOMLine(pn="JOB-PN-1", rev="1", qty=3)]).save()

    _login(client, user)
    resp = client.post(
        "/api/docpacks/build_job",
        data={"job_id": str(job.id), "pdf_binder": "on", "binder_add_cover": ""},
    )
    assert resp.status_code == 200
    assert resp.mimetype == "application/zip"
    with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
        names = zf.namelist()
    assert any(n.startswith("JOB-PN-1") for n in names), names


def test_build_order_docpack_endpoint_end_to_end(app, client, tmp_path):
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    user = _make_user(
        "orders-build@example.com",
        [
            "orders.view",
            "items.view",
            "exports.run",
            "parts.read_unreleased",
        ],
    )
    part = Part(part_number="ORD-PN-1", revision="1", description="Order Part", processes=["machine"]).save()
    pdf_path = os.path.join(root_dir, "ORD-PN-1.pdf")
    _write_pdf(pdf_path, "ORDER PART PDF")
    PartFile(part_number=part.part_number, revision="1", ext_group="pdf", ext="pdf",
              rel_path="ORD-PN-1.pdf", path=pdf_path).save()

    order = Order(order_number="ORD-BUILD-1", lines=[OrderLine(pn="ORD-PN-1", rev="1", qty=2)]).save()

    _login(client, user)
    resp = client.post(
        "/api/docpacks/build_order",
        data={"order_id": str(order.id), "excel_bom": "on"},
    )
    assert resp.status_code == 200
    assert resp.mimetype == "application/zip"
    with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
        names = zf.namelist()
    assert any(n.startswith("ORD-PN-1") for n in names), names


def test_order_scope_pdf_endpoint_still_works(app, client, tmp_path):
    """Regression check that restyling the Scope of Supply form didn't change
    any of its field names -- the view's boolean parsing is untouched, but a
    typo in a `name=` attribute during the restyle would silently break it.
    """
    root_dir = tmp_path
    app.config["FILE_ROOT_LOCAL"] = str(root_dir)

    user = _make_user(
        "scope-build@example.com",
        [
            "orders.view",
            "orders.manage",
            "customers.view",
            "items.view",
            "exports.run",
            "parts.read_unreleased",
        ],
    )
    customer = Customer(name="Acme").save()
    order = Order(order_number="ORD-SCOPE-1", customer=customer, status="submitted", kind="sales",
                  lines=[OrderLine(pn="ORD-SCOPE-PN", rev="1", qty=1)]).save()
    Part(
        part_number="ORD-SCOPE-PN",
        revision="1",
        description="Scope Part",
    ).save()

    _login(client, user)
    resp = client.post(f"/admin/orders/{order.id}/scope_pdf", data={})
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"

    resp2 = client.post(
        f"/admin/orders/{order.id}/scope_pdf",
        data={"attach_docs": "on"},
    )
    assert resp2.status_code == 200
    assert resp2.mimetype == "application/zip"
