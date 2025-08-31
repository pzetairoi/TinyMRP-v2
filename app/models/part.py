# app/models/part.py
from mongoengine import Document, StringField, ListField, DictField, DateTimeField
from datetime import datetime

DB_ALIAS = "tinymrp-v2"

class Part(Document):
    part_number = StringField(required=True)
    revision    = StringField(default="")
    description = StringField(default="")
    processes   = ListField(StringField(), default=list)
    category    = StringField(default="")
    uom         = StringField(default="EA")
    manufacturer= StringField(default="")
    mfr_part    = StringField(default="")
    status      = StringField(default="active")
    docs        = ListField(StringField())
    attrs       = DictField()
    created_at  = DateTimeField(default=datetime.utcnow)
    updated_at  = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "parts",
        "indexes": [
            { "fields": ["part_number", "revision"], "unique": True, "name": "unique_part_rev" },
        ],
        "db_alias": DB_ALIAS
    }
