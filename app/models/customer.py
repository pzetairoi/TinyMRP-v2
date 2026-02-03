from mongoengine import Document, StringField, ListField, ReferenceField, IntField, FloatField, BooleanField, EmbeddedDocumentField

DB_ALIAS = "tinymrp-v2"

from .auth import User
from .common import Contact, Address


class Customer(Document):
    code        = StringField()
    name        = StringField(required=True, unique=True)
    description = StringField()
    is_company  = BooleanField(default=True)
    status      = StringField(default="active")  # active | inactive | prospect | on_hold
    customer_type = StringField(default="oem")  # retail | wholesale | oem | distributor
    segment     = StringField()
    tags        = ListField(StringField(), default=list)
    contact     = StringField()
    email       = StringField()
    website     = StringField()
    phone       = StringField()
    billing_address = EmbeddedDocumentField(Address)
    shipping_addresses = ListField(EmbeddedDocumentField(Address), default=list)
    default_shipping_label = StringField()
    tax_id      = StringField()
    payment_terms = StringField()
    credit_limit = FloatField()
    discount_pct = FloatField()
    currency    = StringField(default="USD")
    sales_rep   = StringField()
    industry    = StringField()
    contacts    = ListField(EmbeddedDocumentField(Contact), default=list)
    users       = ListField(ReferenceField(User), default=list)  # customer-side users

    meta = {
        "collection": "customers",
        "indexes": ["name", "code", "status", "customer_type"],
        "db_alias": DB_ALIAS,
    }
