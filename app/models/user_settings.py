from mongoengine import Document, DictField, StringField, DateTimeField, ReferenceField
from app.models.auth import User
from app.services.timezone_utils import utc_now

DB_ALIAS = "tinymrp-v2"


class UserSettings(Document):
    user_id = ReferenceField(User, required=True, unique=True)
    default_scheme_id = StringField(default="")
    default_context = DictField(default=dict)
    sw_property_map = DictField(default=dict)
    apply_mode = StringField(default="active_config")
    profile = DictField(default=dict)
    ui_preferences = DictField(default=dict)
    field_preferences = DictField(default=dict)
    updated_at = DateTimeField(default=utc_now)

    meta = {
        "collection": "user_settings",
        "indexes": [
            {"fields": ["user_id"], "unique": True, "name": "unique_user_settings"},
        ],
        "db_alias": DB_ALIAS,
    }
