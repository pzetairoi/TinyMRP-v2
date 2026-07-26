from mongoengine import Document, StringField, ListField, ReferenceField, IntField, FloatField, EmbeddedDocumentField

DB_ALIAS = "tinymrp-v2"

from .auth import User
from .common import Contact, Address


class Supplier(Document):
    code        = StringField()
    name        = StringField(required=True, unique=True)
    description = StringField()
    status      = StringField(default="active")  # active | inactive | pending | blacklisted
    rating      = IntField(min_value=1, max_value=5)
    tags        = ListField(StringField(), default=list)
    categories  = ListField(StringField(), default=list)
    contact     = StringField()
    email       = StringField()
    phone       = StringField()
    website     = StringField()
    tax_id      = StringField()
    payment_terms = StringField()
    currency    = StringField(default="USD")
    min_order_value = FloatField()
    lead_time_days = IntField()
    address     = EmbeddedDocumentField(Address)
    billing_address = EmbeddedDocumentField(Address)
    contacts    = ListField(EmbeddedDocumentField(Contact), default=list)
    processes   = ListField(StringField())
    users       = ListField(ReferenceField(User), default=list)  # users linked to this supplier

    meta = {
        "collection": "suppliers",
        "indexes": ["name", "code", "status", "rating", "users"],
        "db_alias": DB_ALIAS,
    }
