from datetime import datetime

from mongoengine import (
    BooleanField,
    DateTimeField,
    Document,
    EmailField,
    ListField,
    ReferenceField,
    StringField,
    ValidationError,
)
from flask_security import UserMixin, RoleMixin
from app.services.timezone_utils import utc_now

DB_ALIAS = "tinymrp-v2"

class Role(Document, RoleMixin):
    name = StringField(required=True, unique=True)
    display_name = StringField()
    description = StringField()
    permissions = ListField(StringField(), default=[])
    meta = {"collection": "roles",
        "db_alias": DB_ALIAS}

    def clean(self):
        from app.services.permissions import PermissionValidationError, validate_permissions

        try:
            validate_permissions(self.permissions)
        except PermissionValidationError as exc:
            raise ValidationError(str(exc)) from exc

class User(Document, UserMixin):
    email = EmailField(required=True, unique=True)
    password = StringField(required=True)
    active = BooleanField(default=True)
    confirmed_at = DateTimeField()
    fs_uniquifier = StringField(required=True, unique=True)
    roles = ListField(ReferenceField(Role), default=[])
    created_at = DateTimeField(default=utc_now)
    updated_at = DateTimeField(default=utc_now)
    last_login_at = DateTimeField()
    last_login_ip = StringField()
    last_login_ua = StringField()
    password_changed_at = DateTimeField(default=utc_now)
    # Two-factor authentication (Flask-Security TOTP; only used when
    # SECURITY_TWO_FACTOR_ENABLED=true — see app/__init__.py).
    tf_totp_secret = StringField()
    tf_primary_method = StringField()
    tf_phone_number = StringField()
    meta = {"collection": "users",
        "db_alias": DB_ALIAS}
