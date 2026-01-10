import secrets
from datetime import datetime
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, FloatField, ListField, ReferenceField, DateTimeField, IntField, BooleanField

DB_ALIAS = "tinymrp-v2"

from .auth import User
from .supplier import Supplier
from .customer import Customer


class JobBOMLine(EmbeddedDocument):
    pn  = StringField(required=True)
    rev = StringField(default="")
    qty = FloatField(default=1.0)


class JobStage(EmbeddedDocument):
    stage_id = StringField(default=lambda: secrets.token_hex(6))
    name = StringField(required=True)
    sequence = IntField(default=1)
    status = StringField(default="pending")  # pending | in_progress | complete | blocked
    assigned_to = StringField()
    department = StringField()
    started_at = DateTimeField()
    completed_at = DateTimeField()
    estimated_hours = FloatField()
    actual_hours = FloatField()
    note = StringField()


class JobNote(EmbeddedDocument):
    ts = DateTimeField(default=datetime.utcnow)
    author = StringField()
    note = StringField()


class Job(Document):
    job_number  = StringField(required=True, unique=True)
    title       = StringField()
    description = StringField()
    part_number = StringField()
    part_revision = StringField()
    qty_ordered = FloatField(default=0.0)
    qty_produced = FloatField(default=0.0)
    qty_scrapped = FloatField(default=0.0)
    status       = StringField(default="draft")  # draft | released | in_progress | on_hold | completed | cancelled
    priority     = StringField(default="normal")  # low | normal | high | urgent
    scheduled_start = DateTimeField()
    scheduled_end   = DateTimeField()
    actual_start = DateTimeField()
    actual_end   = DateTimeField()
    order_number = StringField()
    material_reserved = BooleanField(default=False)
    estimated_hours = FloatField()
    actual_hours    = FloatField()
    participants = ListField(ReferenceField(User), default=list)
    vendors      = ListField(ReferenceField(Supplier), default=list)
    customer     = ReferenceField(Customer)
    bom          = ListField(EmbeddedDocumentField(JobBOMLine), default=list)
    stages       = ListField(EmbeddedDocumentField(JobStage), default=list)
    notes        = ListField(EmbeddedDocumentField(JobNote), default=list)
    is_deleted   = BooleanField(default=False)
    created_at   = DateTimeField(default=datetime.utcnow)
    updated_at   = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "jobs",
        "indexes": ["job_number", "status", "priority", "scheduled_start", "created_at"],
        "db_alias": DB_ALIAS,
    }
