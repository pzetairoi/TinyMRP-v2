"""Seed the worked ordering example the Help screenshots are taken from.

Run against a disposable instance seeded with `flask demo install` - never the
development instance, whose database holds real part numbers.

The demo dataset's own jobs are already bought out, which makes them useless for
showing progressive ordering. This adds one job with nothing ordered against it
yet and two roots that share a subtree, so `Parts Not Yet Ordered` demonstrates
both consolidation (Flat) and per-occurrence level paths (Tree):

    JOB-2026-014
      CV03-TR-A01 rev A  x2   complete trailers
      CV03-F01    rev A  x1   spare core frame

CV03-F01 sits inside CV03-TR-A01 as well as being a root of its own, so every
frame part is required through two different parents and lands in the flat view
as a single consolidated line. Both roots are approved, so the example reads the
same for every role; the dataset's deliberately unapproved parts (CV03-F02 rev B
and ADR-LED-IND) stay inside the tree, where they demonstrate the approval
boundary instead of obscuring the worked example.

Idempotent: the job and any order raised against it are removed and rebuilt, so
a capture run always starts from the same state.

    ENV_FILE=<instance env> python frontend/tools/seed-help-job.py
"""

from __future__ import annotations

import sys

from app import create_app

JOB_NUMBER = "JOB-2026-014"
JOB_TITLE = "CELLV03 build - two trailers and a spare core frame"
CUSTOMER_CODE = "DEMO-CUST-A"
ROOTS = (("CV03-TR-A01", "A", 2.0), ("CV03-F01", "A", 1.0))


def main() -> int:
    app = create_app()
    with app.app_context():
        from app.models.customer import Customer
        from app.models.job import Job, JobBOMLine
        from app.models.order import Order
        from app.models.part import Part

        missing = [
            f"{pn} rev {rev}"
            for pn, rev, _qty in ROOTS
            if Part.objects(part_number=pn, revision=rev).first() is None
        ]
        if missing:
            print(f"Sample dataset not installed; missing {', '.join(missing)}.")
            print("Run: flask demo install --domain demo.com")
            return 1

        existing = Job.objects(job_number=JOB_NUMBER).first()
        if existing:
            Order.objects(job=existing).delete()
            existing.delete()

        job = Job(
            job_number=JOB_NUMBER,
            title=JOB_TITLE,
            description=(
                "Two complete trailers for stock plus one spare core frame. "
                "Nothing ordered yet - the worked example in Help Workflow B."
            ),
            status="planned",
            priority="normal",
            customer=Customer.objects(code=CUSTOMER_CODE).first(),
            bom=[JobBOMLine(pn=pn, rev=rev, qty=qty) for pn, rev, qty in ROOTS],
        )
        job.save()
        print(f"Seeded {JOB_NUMBER} ({job.id}) with {len(job.bom)} BOM roots.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
