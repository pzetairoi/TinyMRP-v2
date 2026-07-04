from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, ReferenceField
from app.models.part import Part
from app.services.timezone_utils import utc_now

DB_ALIAS = "tinymrp-v2"


class PartRevisionHistory(Document):
    part_id = ReferenceField(Part)
    part_number = StringField(required=True)
    revision = StringField(default="")
    status = StringField(default="WIP")
    change_note = StringField(default="")
    created_at = DateTimeField(default=utc_now)
    created_by = StringField(default="")

    meta = {
        "collection": "part_revision_history",
        "indexes": [
            "part_number",
            ("part_number", "revision"),
            "created_at",
        ],
        "db_alias": DB_ALIAS,
    }
