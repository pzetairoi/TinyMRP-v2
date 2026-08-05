from mongoengine import Document, StringField, DateTimeField, DictField
from app.services.timezone_utils import utc_now

DB_ALIAS = "tinymrp-v2"


class AuditLog(Document):
    """Simple audit log of user actions for access and operations.

    Fields:
    - ts: UTC timestamp
    - user_id: string of the user's id (ObjectId string) if available
    - email: user email at time of action
    - roles: comma-separated role names (snapshot)
    - action: short keyword like 'part.view', 'bom.view', 'docpack.build', 'file.view'
    - resource_type: e.g. 'part', 'bom', 'file'
    - resource: freeform identifier (like PN:REV, or rel path)
    - ip: remote ip address
    - ua: user-agent string (truncated if needed)
    - method: HTTP method (GET/POST/etc)
    - endpoint: request path (e.g., /downloads/macro)
    - meta: optional dictionary with extra details
    """

    ts = DateTimeField(default=utc_now)
    user_id = StringField()
    email = StringField()
    roles = StringField()
    action = StringField(required=True)
    resource_type = StringField()
    resource = StringField()
    ip = StringField()
    ua = StringField()
    method = StringField()
    endpoint = StringField()
    # Use 'extra' instead of 'meta' to avoid clashing with MongoEngine's meta options
    extra = DictField()

    meta = {
        "collection": "audit_logs",
        "indexes": [
            "-ts",
            "action",
            "email",
            "ip",
            "endpoint",
            "method",
            "user_id",
        ],
        "db_alias": DB_ALIAS,
    }
