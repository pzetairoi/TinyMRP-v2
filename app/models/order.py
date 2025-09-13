from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, FloatField, ListField, ReferenceField, DateTimeField
from datetime import datetime

DB_ALIAS = "tinymrp-v2"

from .job import Job
from .supplier import Supplier
from .customer import Customer


class OrderLine(EmbeddedDocument):
    pn   = StringField(required=True)
    rev  = StringField(default="")
    qty  = FloatField(default=1.0)
    uom  = StringField(default="EA")
    note = StringField()


class Order(Document):
    order_number = StringField(required=True, unique=True)
    description  = StringField()
    kind         = StringField(default="purchase")  # purchase | work
    job          = ReferenceField(Job)
    supplier     = ReferenceField(Supplier)
    customer     = ReferenceField(Customer)
    lines        = ListField(EmbeddedDocumentField(OrderLine), default=list)
    status       = StringField(default="open")
    created_at   = DateTimeField(default=datetime.utcnow)
    updated_at   = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "orders",
        "indexes": ["order_number", "kind", "status"],
        "db_alias": DB_ALIAS,
    }

