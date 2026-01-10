from datetime import datetime

from app.models.part import Part
from app.models.artifact import PartFile
from app.models.bom import BOMLink
from app.models.job import Job, JobBOMLine
from app.models.order import Order, OrderLine
from app.models.part_revision import PartRevisionHistory
from app.services.biz_utils import calculate_order_totals
from app.services.parts_delete import delete_part_and_refs


def test_delete_part_and_refs(app):
    with app.app_context():
        Part(part_number="PN-100", revision="A", description="Root").save()
        Part(part_number="PN-200", revision="", description="Other").save()
        PartFile(
            part_number="PN-100",
            revision="A",
            ext_group="png",
            ext="png",
            rel_path="thumbs/PN-100.png",
            path="C:/tmp/PN-100.png",
        ).save()
        PartRevisionHistory(part_number="PN-100", revision="A", created_at=datetime.utcnow()).save()
        BOMLink(parent_pn="PN-100", parent_rev="A", child_pn="PN-200", child_rev="", qty=1).save()
        BOMLink(parent_pn="PN-300", parent_rev="", child_pn="PN-100", child_rev="A", qty=2).save()

        job = Job(job_number="JOB-1", bom=[JobBOMLine(pn="PN-100", rev="A", qty=2), JobBOMLine(pn="PN-200", rev="", qty=1)]).save()

        line1 = OrderLine(pn="PN-100", rev="A", qty=2, unit_price=10.0)
        line2 = OrderLine(pn="PN-200", rev="", qty=1, unit_price=5.0)
        subtotal, tax_amount, discount_amount = calculate_order_totals([line1, line2])
        order = Order(
            order_number="PO-1",
            lines=[line1, line2],
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            total=subtotal - discount_amount + tax_amount,
        ).save()

        result = delete_part_and_refs("PN-100", "A")
        assert result["deleted_parts"] == 1
        assert result["deleted_files"] == 1
        assert result["deleted_bom_links"] == 2
        assert result["deleted_revisions"] == 1
        assert result["updated_jobs"] == 1
        assert result["updated_orders"] == 1

        assert Part.objects(part_number="PN-100", revision="A").count() == 0
        assert PartFile.objects(part_number="PN-100", revision="A").count() == 0
        assert BOMLink.objects(parent_pn="PN-100", parent_rev="A").count() == 0
        assert BOMLink.objects(child_pn="PN-100", child_rev="A").count() == 0
        assert PartRevisionHistory.objects(part_number="PN-100", revision="A").count() == 0

        job.reload()
        assert all((l.pn or "").upper() != "PN-100" for l in (job.bom or []))

        order.reload()
        assert all((l.pn or "").upper() != "PN-100" for l in (order.lines or []))
        assert order.total == 5.0
