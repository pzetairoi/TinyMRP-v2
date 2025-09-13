from mongoengine import Document, StringField, ListField, ReferenceField

DB_ALIAS = "tinymrp-v2"

from .auth import User


class Customer(Document):
    name        = StringField(required=True, unique=True)
    description = StringField()
    contact     = StringField()
    email       = StringField()
    phone       = StringField()
    address     = StringField()
    users       = ListField(ReferenceField(User), default=list)  # customer-side users

    meta = {
        "collection": "customers",
        "indexes": ["name"],
        "db_alias": DB_ALIAS,
    }

