
from mongoengine import BooleanField, DateTimeField, Document, IntField, StringField
from app.services.timezone_utils import utc_now


DB_ALIAS = "tinymrp-v2"


class PartShareLink(Document):
    part_number = StringField(required=True)
    revision = StringField(default="")
    token_hash = StringField(required=True, unique=True)
    token_prefix = StringField(required=True)
    allow_children = BooleanField(default=False)
    allow_docpacks = BooleanField(default=False)
    allow_attributes = BooleanField(default=False)
    allow_unreleased = BooleanField(default=False)
    # The four file-exposure grants below are tri-state ON PURPOSE. A share
    # created before access levels existed has no such field, which reads back
    # as None, and None means "this link predates the levels, keep granting
    # what it already granted". Every share created since stores an explicit
    # boolean, so a link sitting in someone's inbox never quietly shows less
    # than it did when it was sent, and no data migration is needed to deploy.
    allow_drawings = BooleanField(null=True, default=None)
    allow_neutral_cad = BooleanField(null=True, default=None)
    allow_datasheets = BooleanField(null=True, default=None)
    allow_all_files = BooleanField(null=True, default=None)
    enabled = BooleanField(default=True)
    created_at = DateTimeField(default=utc_now)
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
