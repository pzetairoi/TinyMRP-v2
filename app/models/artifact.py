from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, IntField, DictField

DB_ALIAS = "tinymrp-v2"

class PartFile(Document):
    part_number = StringField(required=True)
    revision    = StringField(default="")
    ext_group   = StringField(required=True, choices=["pdf","dxf","step","edr","png","3mf","other"])
    ext         = StringField(required=True)
    path        = StringField(required=True, unique=True)   # absolute OS path
    rel_path    = StringField()                             # relative to FILE_ROOT_LOCAL
    size        = IntField()
    sha256      = StringField()
    mtime       = DateTimeField()
    content_type= StringField()
    source      = StringField(default="scan")
    meta_info   = DictField()
    discovered_at = DateTimeField(default=datetime.utcnow)

    # ✅ thumbnail bookkeeping (for image artifacts, e.g., ext_group == "png")
    thumb_rel_path = StringField()      # e.g., "thumbs/png/A-B_REV_1.png"
    thumb_mtime    = DateTimeField()    # mtime of generated thumbnail

    meta = {
        "collection": "part_files",
        "db_alias": DB_ALIAS,
        "indexes": [
            {"fields": ["part_number", "revision", "ext_group"]},
            "rel_path",
            "thumb_rel_path",
        ],
    }
