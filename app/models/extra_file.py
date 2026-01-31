from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, FloatField


DB_ALIAS = "tinymrp-v2"


class PartExtraFile(Document):
    part_number = StringField(required=True)
    revision = StringField(default="")
    original_name = StringField(required=True)
    rel_path = StringField(required=True)
    size = FloatField()
    mime = StringField()
    sha256 = StringField()
    label = StringField()
    uploaded_by = StringField()
    uploaded_at = DateTimeField(default=datetime.utcnow)
    source = StringField(default="upload")

    meta = {
        "collection": "part_extra_files",
        "db_alias": DB_ALIAS,
        "indexes": [
            {"fields": ["part_number", "revision"]},
            {"fields": ["part_number", "revision", "original_name"]},
        ],
    }
