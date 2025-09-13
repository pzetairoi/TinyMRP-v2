from mongoengine import Document, StringField, ListField, ReferenceField

DB_ALIAS = "tinymrp-v2"

from .auth import User


class Supplier(Document):
    name        = StringField(required=True, unique=True)
    description = StringField()
    contact     = StringField()
    email       = StringField()
    phone       = StringField()
    processes   = ListField(StringField())
    users       = ListField(ReferenceField(User), default=list)  # users linked to this supplier

    meta = {
        "collection": "suppliers",
        "indexes": ["name"],
        "db_alias": DB_ALIAS,
    }

