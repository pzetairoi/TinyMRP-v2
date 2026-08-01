from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, FloatField, ListField, ReferenceField, DateTimeField, IntField, NULLIFY
from datetime import datetime

DB_ALIAS = "tinymrp-v2"

from .job import Job
from .supplier import Supplier
from .customer import Customer
from .common import Address
from app.services.timezone_utils import utc_now


class OrderLine(EmbeddedDocument):
    pn   = StringField(required=True)
    rev  = StringField(default="")
    qty  = FloatField(default=1.0)
    uom  = StringField(default="EA")
    note = StringField()
    description = StringField()
    unit_price = FloatField(default=0.0)
    discount_pct = FloatField(default=0.0)
    tax_pct = FloatField(default=0.0)
    line_total = FloatField(default=0.0)
    qty_shipped = FloatField(default=0.0)
    qty_received = FloatField(default=0.0)
    requested_delivery = DateTimeField()


class Order(Document):
    order_number = StringField(required=True, unique=True)
    description  = StringField()
    kind         = StringField(default="purchase")  # purchase | sales
    # Deleting a Job clears the link instead of leaving a dangling DBRef that
    # raises DoesNotExist when any order row is rendered.
    job          = ReferenceField(Job, reverse_delete_rule=NULLIFY)
    supplier     = ReferenceField(Supplier)
    customer     = ReferenceField(Customer)
    lines        = ListField(EmbeddedDocumentField(OrderLine), default=list)
    status       = StringField(default="draft")
    customer_po  = StringField()
    order_date   = DateTimeField(default=utc_now)
    requested_delivery = DateTimeField()
    promised_delivery = DateTimeField()
    actual_delivery = DateTimeField()
    subtotal     = FloatField(default=0.0)
    tax_amount   = FloatField(default=0.0)
    shipping_cost = FloatField(default=0.0)
    discount_amount = FloatField(default=0.0)
    total        = FloatField(default=0.0)
    currency     = StringField(default="USD")
    shipping_address = EmbeddedDocumentField(Address)
    shipping_method = StringField()
    carrier      = StringField()
    tracking_number = StringField()
    approved_by  = StringField()
    approved_at  = DateTimeField()
    rejection_reason = StringField()
    created_at   = DateTimeField(default=utc_now)
    updated_at   = DateTimeField(default=utc_now)

    meta = {
        "collection": "orders",
        "indexes": [
            "order_number", "kind", "status", "order_date", "job",
            ("kind", "customer"), ("kind", "supplier"),
        ],
        "db_alias": DB_ALIAS,
    }
