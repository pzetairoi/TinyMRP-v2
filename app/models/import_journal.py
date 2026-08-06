from mongoengine import (
    BooleanField,
    DateTimeField,
    DictField,
    Document,
    IntField,
    ListField,
    StringField,
)

from app.services.timezone_utils import utc_now

DB_ALIAS = "tinymrp-v2"


class ImportJournal(Document):
    """Durable record of one upload-pack import attempt (IMPORT-ATOMIC-01).

    Upload-pack import writes across two stores that cannot share a
    transaction: MongoDB (parts, BOM links, file records) and the filesystem
    (deliverables). The file commit already rolls itself back on failure, but
    the database writes that preceded it do not, so a failure part-way through
    used to leave changed data with no record of what had landed.

    This journal is written BEFORE any effect is applied and updated as the
    import progresses, so a failed or interrupted run can always be
    reconciled. It is deliberately a record rather than a lock: it does not
    prevent a partial import, it makes one diagnosable and recoverable.

    Statuses
      started    effects are about to be applied
      committed  every stage completed
      failed     a stage raised; `error` and `stage` say where
      rolled_back  compensating actions completed after a failure

    `operation_id` is unique per attempt and is returned to the caller so an
    operator can find the record for a specific import.
    """

    operation_id = StringField(required=True, unique=True)

    # Content+options fingerprint, so re-running the SAME pack with the SAME
    # policies can be recognised as a repeat rather than duplicating work.
    # Not unique: a deliberate re-import is legitimate, and the caller decides.
    idempotency_key = StringField(default="")
    status = StringField(required=True, default="started")
    stage = StringField(default="")

    started_at = DateTimeField(default=utc_now)
    finished_at = DateTimeField()

    filename = StringField(default="")
    uploaded_by = StringField(default="")
    seed_tag = StringField(default="")
    dry_run = BooleanField(default=False)

    # What the plan intended, captured before execution.
    planned_parts = IntField(default=0)
    planned_files = IntField(default=0)

    # What actually landed. Populated as each stage completes so the record is
    # useful even when the process dies mid-import.
    parts_created = IntField(default=0)
    parts_updated = IntField(default=0)
    links_created = IntField(default=0)
    files_written = IntField(default=0)

    # Identities touched, so an operator can reconcile precisely rather than
    # guessing from counts. "PN\x1frev" pairs.
    touched_parts = ListField(StringField())

    # Compensating actions performed after a failure, and anything that could
    # not be undone and therefore needs manual attention.
    rollback_actions = ListField(StringField())
    manual_followup = ListField(StringField())

    error = StringField(default="")

    # Free-form extra context. Named `details` rather than `meta` because
    # mongoengine reserves `meta` for document configuration.
    details = DictField()

    meta = {
        "db_alias": DB_ALIAS,
        "collection": "import_journal",
        "indexes": ["operation_id", "idempotency_key", "status", "-started_at"],
    }
