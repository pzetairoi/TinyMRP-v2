from mongoengine import Document, StringField, DateTimeField, ReferenceField
from app.models.auth import User
from app.services.timezone_utils import utc_now

DB_ALIAS = "tinymrp-v2"


class ApiToken(Document):
    user_id = ReferenceField(User, required=True)
    token_hash = StringField(required=True, unique=True)
    label = StringField(default="", max_length=120)
    created_at = DateTimeField(default=utc_now)
    last_used_at = DateTimeField()
    revoked_at = DateTimeField()
    revocation_reason = StringField(default="", max_length=80)
    expires_at = DateTimeField()

    meta = {
        "collection": "api_tokens",
        "indexes": [
            {"fields": ["token_hash"], "unique": True, "name": "unique_token_hash"},
            "user_id",
            "created_at",
            {"fields": ["user_id", "revoked_at", "expires_at"], "name": "token_lifecycle"},
        ],
        "db_alias": DB_ALIAS,
    }
