from datetime import datetime
from mongoengine import Document, StringField, DateTimeField

DB_ALIAS = "tinymrp-v2"


class AppSettings(Document):
    brand_logo_rel_path = StringField(default="")
    timezone = StringField(default="")
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "app_settings",
        "db_alias": DB_ALIAS,
    }
