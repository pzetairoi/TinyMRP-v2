from datetime import datetime

from mongoengine import Document, StringField, EmailField, BooleanField, DateTimeField, ListField, ReferenceField
from flask_security import UserMixin, RoleMixin

DB_ALIAS = "tinymrp-v2"

class Role(Document, RoleMixin):
    name = StringField(required=True, unique=True)
    description = StringField()
    permissions = ListField(StringField(), default=[])
    meta = {"collection": "roles",
        "db_alias": DB_ALIAS}

class User(Document, UserMixin):
    email = EmailField(required=True, unique=True)
    password = StringField(required=True)
    active = BooleanField(default=True)
    confirmed_at = DateTimeField()
    fs_uniquifier = StringField(required=True, unique=True)
    roles = ListField(ReferenceField(Role), default=[])
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    last_login_at = DateTimeField()
    last_login_ip = StringField()
    last_login_ua = StringField()
    password_changed_at = DateTimeField(default=datetime.utcnow)
    meta = {"collection": "users",
        "db_alias": DB_ALIAS}
