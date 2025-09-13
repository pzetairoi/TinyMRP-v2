from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, FloatField, ListField, ReferenceField

DB_ALIAS = "tinymrp-v2"

from .auth import User
from .supplier import Supplier
from .customer import Customer


class JobBOMLine(EmbeddedDocument):
    pn  = StringField(required=True)
    rev = StringField(default="")
    qty = FloatField(default=1.0)


class Job(Document):
    job_number  = StringField(required=True, unique=True)
    description = StringField()
    participants = ListField(ReferenceField(User), default=list)
    vendors      = ListField(ReferenceField(Supplier), default=list)
    customer     = ReferenceField(Customer)
    bom          = ListField(EmbeddedDocumentField(JobBOMLine), default=list)
    status       = StringField(default="open")

    meta = {
        "collection": "jobs",
        "indexes": ["job_number"],
        "db_alias": DB_ALIAS,
    }
