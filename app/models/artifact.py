from datetime import datetime
from mongoengine import FloatField, BooleanField, Document, StringField, DateTimeField, IntField, DictField
from app.services.timezone_utils import utc_now
 


DB_ALIAS = "tinymrp-v2"

class PartFile(Document):
    part_number = StringField(required=True)
    revision    = StringField(default="")  # empty revision allowed
    ext_group   = StringField(required=True)  # e.g. 'png','pdf','step','dxf','edr','3mf','datasheet'
    ext         = StringField(required=True)  # actual extension
    rel_path    = StringField(required=True)  # relative to FILE_ROOT_LOCAL
    http_url    = StringField()               # prebuilt http absolute url
    size        = FloatField()
    mtime_iso   = DateTimeField()
    is_dwg      = BooleanField(default=False) # <-- key: distinguishes *_DWG.png    
    path        = StringField(required=True, unique=True)   # absolute OS path
    sha256      = StringField()
    mtime       = DateTimeField()
    content_type= StringField()
    source      = StringField(default="scan")
    meta_info   = DictField()
    discovered_at = DateTimeField(default=utc_now)

    # ✅ thumbnail bookkeeping (for image artifacts, e.g., ext_group == "png")
    thumb_rel_path = StringField()      # e.g., "thumbs/png/A-B_REV_1.png"
    thumb_mtime    = DateTimeField()    # mtime of generated thumbnail

    meta = {
        "collection": "part_files",
        "db_alias": DB_ALIAS,
    "indexes": [
        # unique identity for an artifact type per PN+REV
        {"fields": ["part_number", "revision", "ext_group", "ext","is_dwg"], "unique": True},
        {"fields": ["ext_group", "part_number", "revision"], "name": "part_files_ext_group_part_rev_idx"},
    ]
}
