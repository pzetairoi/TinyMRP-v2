from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, IntField, DictField

DB_ALIAS = "tinymrp-v2"  # keep aligned with your other models

class PartFile(Document):
    part_number = StringField(required=True)      # e.g., "AWS-B-008968"
    revision    = StringField(default="")         # normalized (e.g., "A", "1")
    ext_group   = StringField(required=True, choices=["pdf","dxf","step","edr","png","3mf","other"])
    ext         = StringField(required=True)      # actual extension, e.g., ".pdf"
    path        = StringField(required=True)      # absolute OS/UNC path
    size        = IntField()                      # bytes
    sha256      = StringField()                   # optional checksum (see config below)
    mtime       = DateTimeField()                 # file modification time (UTC)
    source      = StringField(default="scan")     # "scan" | "upload" | etc
    meta_info   = DictField()                     # room for viewers/derived data
    discovered_at = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "part_files",
        "db_alias": DB_ALIAS,
        "indexes": [
            {"fields": ["part_number", "revision", "ext_group"]},
            {"fields": ["path"], "unique": True},
        ],
    }
