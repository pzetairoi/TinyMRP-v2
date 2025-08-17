# app/models/artifact.py
from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, IntField, DictField

DB_ALIAS = "tinymrp-v2"

class PartFile(Document):
    part_number = StringField(required=True)
    revision    = StringField(default="")
    ext_group   = StringField(required=True, choices=["pdf","dxf","step","edr","png","3mf","other"])
    ext         = StringField(required=True)           # ".pdf", ".png", ...
    path        = StringField(required=True, unique=True)  # absolute OS/UNC path
    rel_path    = StringField()                        # relative to FILE_ROOTS_JSON[i].local
    root_idx    = IntField(default=0)                  # index in FILE_ROOTS_JSON
    size        = IntField()
    sha256      = StringField()
    mtime       = DateTimeField()
    content_type= StringField()
    source      = StringField(default="scan")
    meta_info   = DictField()
    discovered_at = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "part_files",
        "db_alias": DB_ALIAS,
        "indexes": [
            {"fields": ["part_number", "revision", "ext_group"]},
            "rel_path",
        ],
    }
