# app/models/part.py
from mongoengine import Document, StringField, ListField, DictField, DateTimeField
from datetime import datetime

DB_ALIAS = "tinymrp-v2"

class Part(Document):
    part_number = StringField(required=True, unique=True)
    revision    = StringField(default="")
    description = StringField(default="")
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
            "part_number","category","uom","status",
            {"fields": ["$part_number","$description","$manufacturer","$mfr_part"],
             "default_language": "english"},
        ],
        "db_alias": DB_ALIAS
    }
