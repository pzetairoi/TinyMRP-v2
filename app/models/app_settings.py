from mongoengine import (
    BooleanField,
    DateTimeField,
    DictField,
    Document,
    IntField,
    ListField,
    StringField,
)
from app.services.timezone_utils import utc_now

DB_ALIAS = "tinymrp-v2"


class AppSettings(Document):
    brand_logo_rel_path = StringField(default="")
    # Tri-state ON PURPOSE: None means "never set from the dashboard, use the
    # ALLOW_PERMISSION_TEST_DATA environment variable". True/False are an
    # explicit administrator decision and win over the environment.
    # A plain False default would silently switch off every instance that
    # currently enables the flag through its .env the moment this field is
    # added.
    allow_permission_test_data = BooleanField(default=None, null=True)
    # Backups. Empty/zero means "use the schedule the host already has";
    # these only describe what the dashboard asks for.
    backup_schedule_hour_utc = IntField(default=None, null=True)
    backup_retention_days = IntField(default=None, null=True)
    timezone = StringField(default="")
    arena_file_link_base_url = StringField(default="")
    hardware_folders = ListField(StringField(), default=list)
    flat_pattern_page_names = ListField(StringField(), default=list)
    upload_pack_max_zip_mb = IntField(default=1024)
    upload_pack_max_file_mb = IntField(default=1024)
    upload_pack_max_files = IntField(default=5000)
    file_sources = ListField(DictField(), default=list)
    field_config = DictField(default=dict)
    process_meta = DictField(default=dict)
    updated_at = DateTimeField(default=utc_now)

    meta = {
        "collection": "app_settings",
        "db_alias": DB_ALIAS,
    }
