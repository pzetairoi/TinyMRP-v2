from mongoengine import DateTimeField, Document, ReferenceField, StringField

from app.models.auth import User
from app.services.timezone_utils import utc_now


DB_ALIAS = "tinymrp-v2"


class UserNotification(Document):
    recipient = ReferenceField(User, required=True)
    actor_email = StringField(default="")
    kind = StringField(required=True, choices=("mention", "part_review", "thread_update", "comment_changed"))
    title = StringField(required=True, max_length=180)
    body = StringField(default="", max_length=500)
    url = StringField(required=True, max_length=500)
    part_number = StringField(default="")
    revision = StringField(default="")
    thread_id = StringField(default="")
    comment_id = StringField(default="")
    created_at = DateTimeField(default=utc_now)
    read_at = DateTimeField()

    meta = {
        "collection": "user_notifications",
        "db_alias": DB_ALIAS,
        "indexes": [
            {"fields": ["recipient", "-created_at"], "name": "notification_recipient_created_idx"},
            {"fields": ["recipient", "read_at", "-created_at"], "name": "notification_unread_idx"},
        ],
    }
