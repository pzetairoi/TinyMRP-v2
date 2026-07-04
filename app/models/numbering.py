from datetime import datetime
from mongoengine import (
    Document,
    StringField,
    BooleanField,
    ListField,
    DictField,
    IntField,
    DateTimeField,
)
from app.services.timezone_utils import utc_now

DB_ALIAS = "tinymrp-v2"


class NumberingScheme(Document):
    name = StringField(required=True)
    description = StringField(default="")
    is_active = BooleanField(default=True)
    is_preset = BooleanField(default=False)
    is_recommended = BooleanField(default=False)
    visibility = StringField(default="advanced_only")
    pattern_segments = ListField(DictField(), default=list)
    separator = StringField(default="-")
    scope_mode = StringField(default="global")
    scope_keys = ListField(StringField(), default=list)
    seq = DictField(default=dict)
    revision = DictField(default=dict)
    validation_rules = DictField(default=dict)
    audit = DictField(default=dict)

    meta = {
        "collection": "numbering_schemes",
        "indexes": [
            {"fields": ["name"], "unique": True, "name": "unique_scheme_name"},
        ],
        "db_alias": DB_ALIAS,
    }


class NumberingCounter(Document):
    counter_key = StringField(required=True, unique=True)
    next_value = IntField(default=1)
    updated_at = DateTimeField(default=utc_now)

    meta = {
        "collection": "numbering_counters",
        "indexes": [
            {"fields": ["counter_key"], "unique": True, "name": "unique_counter_key"},
        ],
        "db_alias": DB_ALIAS,
    }
