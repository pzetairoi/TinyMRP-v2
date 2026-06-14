from datetime import datetime

from mongoengine import BooleanField, DateTimeField, Document, IntField, StringField


DB_ALIAS = "tinymrp-v2"


class PartShareLink(Document):
    part_number = StringField(required=True)
    revision = StringField(default="")
    token_hash = StringField(required=True, unique=True)
    token_prefix = StringField(required=True)
    allow_children = BooleanField(default=False)
    allow_docpacks = BooleanField(default=False)
    allow_attributes = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.utcnow)
    created_by_user_id = StringField()
    created_by_email = StringField()
    expires_at = DateTimeField()
    revoked_at = DateTimeField()
    revoked_by_user_id = StringField()
    revoked_by_email = StringField()
    last_accessed_at = DateTimeField()
    last_access_ip = StringField()
    last_access_ua = StringField()
    access_count = IntField(default=0)

    meta = {
        "collection": "part_share_links",
        "db_alias": DB_ALIAS,
        "indexes": [
            {"fields": ["part_number", "revision", "-created_at"]},
            {"fields": ["-created_at"]},
            {"fields": ["expires_at"]},
            {"fields": ["revoked_at"]},
            {"fields": ["created_by_email"]},
        ],
    }
