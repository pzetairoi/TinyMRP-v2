from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, ListField, IntField

DB_ALIAS = "tinymrp-v2"


class AppSettings(Document):
    brand_logo_rel_path = StringField(default="")
    timezone = StringField(default="")
    hardware_folders = ListField(StringField(), default=list)
    flat_pattern_page_names = ListField(StringField(), default=list)
    upload_pack_max_zip_mb = IntField(default=1024)
    upload_pack_max_file_mb = IntField(default=1024)
    upload_pack_max_files = IntField(default=5000)
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "app_settings",
        "db_alias": DB_ALIAS,
    }
