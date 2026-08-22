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
    # Backup policy. The backup itself runs on the HOST - the app container has
    # a read-only backups mount, no docker socket and an unprivileged user, and
    # giving it any of those would make a web RCE a host compromise. So the app
    # owns the POLICY and the host script reads it before each run.
    #
    # None means "not set here": the script keeps whatever its flags or the
    # instance env file gave it. That layering is what lets an existing install
    # keep behaving exactly as it did until somebody deliberately changes
    # something.
    backup_schedule_hour_utc = IntField(default=None, null=True)
    backup_retention_days = IntField(default=None, null=True)
    # Deliverables are the expensive half by three orders of magnitude - a few
    # MB of database against many GB of engineering files - and unlike the
    # database they can be regenerated from CAD. Off unless somebody asks.
    backup_include_deliverables = BooleanField(default=False)
    # weekly | fortnightly | monthly. Only consulted when deliverables are on.
    backup_deliverables_frequency = StringField(default="monthly")
    # Absolute HOST path. Empty keeps them beside the database backups, which
    # means on the same disk as the data they protect - the point of setting
    # this is to put them on another drive.
    backup_deliverables_dest = StringField(default="")
    backup_keep_full = IntField(default=None, null=True)
    backup_keep_db = IntField(default=None, null=True)
    backup_min_free_gb = IntField(default=None, null=True)
    backup_min_free_pct = IntField(default=None, null=True)
    timezone = StringField(default="")
    arena_file_link_base_url = StringField(default="")
    hardware_folders = ListField(StringField(), default=list)
    flat_pattern_page_names = ListField(StringField(), default=list)
    upload_pack_max_zip_mb = IntField(default=1024)
    upload_pack_max_file_mb = IntField(default=1024)
    upload_pack_max_files = IntField(default=5000)
    # Upload packs land in <deliverables>/bom and are never read again once
    # imported. Packs older than this move to bom/archive so the working folder
    # stays legible; nothing is ever deleted. 0 disables the sweep entirely.
    bom_pack_retention_days = IntField(default=7)
    bom_pack_swept_at = DateTimeField()
    # Set once, the first time the built-in numbering scheme is seeded. Seeding
    # is a first-run convenience, not a guarantee: without this marker the boot
    # seeder recreated a scheme the administrator had deliberately deleted.
    numbering_preset_seeded = BooleanField(default=False)
    file_sources = ListField(DictField(), default=list)
    field_config = DictField(default=dict)
    process_meta = DictField(default=dict)
    updated_at = DateTimeField(default=utc_now)

    meta = {
        "collection": "app_settings",
        "db_alias": DB_ALIAS,
    }
