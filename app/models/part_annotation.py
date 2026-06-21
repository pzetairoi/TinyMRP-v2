from datetime import datetime

from mongoengine import DateTimeField, DictField, Document, ListField, StringField


DB_ALIAS = "tinymrp-v2"


class PartAnnotation(Document):
    part_number = StringField(required=True)
    revision = StringField(default="")
    notes = StringField(default="")
    comments = ListField(DictField(), default=list)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "part_annotations",
        "indexes": [
            {"fields": ["part_number", "revision"], "unique": True, "name": "unique_part_annotation_rev"},
            {"fields": ["part_number"], "name": "part_annotation_part_number_idx"},
            {"fields": ["updated_at"], "name": "part_annotation_updated_at_idx"},
        ],
        "db_alias": DB_ALIAS,
    }
