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
            { "fields": ["part_number"], "name": "part_number_idx" },
            { "fields": ["updated_at"], "name": "parts_updated_at_idx" },
            { "fields": ["processes"], "name": "parts_processes_idx" },
            { "fields": ["description"], "name": "parts_description_idx" },
            { "fields": ["attrs.material"], "name": "parts_material_idx" },
            { "fields": ["attrs.finish"], "name": "parts_finish_idx" },
        ],
        "db_alias": DB_ALIAS
    }

    @property
    def display_code(self) -> str:
        if self.revision:
            return f"{self.part_number}-{self.revision}"
        return self.part_number
