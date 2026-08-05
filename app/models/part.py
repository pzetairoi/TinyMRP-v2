# app/models/part.py
from mongoengine import BooleanField, DateTimeField, DictField, Document, IntField, ListField, StringField
from app.services.timezone_utils import utc_now

DB_ALIAS = "tinymrp-v2"

class Part(Document):
    part_number = StringField(required=True)
    revision    = StringField(default="")
    description = StringField(default="")
    processes   = ListField(StringField(), default=list)
    canonical   = DictField(default=dict)
    field_values = DictField(default=dict)
    category    = StringField(default="")
    uom         = StringField(default="EA")
    manufacturer= StringField(default="")
    mfr_part    = StringField(default="")
    status      = StringField(default="active")
    docs        = ListField(StringField())
    attrs       = DictField()
    file_groups = ListField(StringField(), default=list)
    has_pdf = BooleanField(default=False)
    has_png = BooleanField(default=False)
    has_dxf = BooleanField(default=False)
    has_step = BooleanField(default=False)
    has_edr = BooleanField(default=False)
    has_3mf = BooleanField(default=False)
    has_ply = BooleanField(default=False)
    has_stl = BooleanField(default=False)
    has_datasheet = BooleanField(default=False)
    notes_search = StringField(default="")
    comments_search = StringField(default="")
    pending_review_count = IntField(default=0)
    pending_review_severity = StringField(default="")
    created_at  = DateTimeField(default=utc_now)
    updated_at  = DateTimeField(default=utc_now)

    meta = {
        "collection": "parts",
        "indexes": [
            { "fields": ["part_number", "revision"], "unique": True, "name": "unique_part_rev" },
            { "fields": ["part_number"], "name": "part_number_idx" },
            { "fields": ["revision"], "name": "parts_revision_idx" },
            { "fields": ["updated_at"], "name": "parts_updated_at_idx" },
            { "fields": ["created_at"], "name": "parts_created_at_idx" },
            { "fields": ["processes"], "name": "parts_processes_idx" },
            { "fields": ["description"], "name": "parts_description_idx" },
            { "fields": ["notes_search"], "name": "parts_notes_search_idx" },
            { "fields": ["comments_search"], "name": "parts_comments_search_idx" },
            { "fields": ["pending_review_count"], "name": "parts_pending_review_count_idx" },
            { "fields": ["pending_review_severity"], "name": "parts_pending_review_severity_idx" },
            { "fields": ["category"], "name": "parts_category_idx" },
            { "fields": ["status"], "name": "parts_status_idx" },
            { "fields": ["manufacturer"], "name": "parts_manufacturer_idx" },
            { "fields": ["mfr_part"], "name": "parts_mfr_part_idx" },
            { "fields": ["canonical.material"], "name": "parts_canonical_material_idx" },
            { "fields": ["canonical.finish"], "name": "parts_canonical_finish_idx" },
            { "fields": ["canonical.mass"], "name": "parts_canonical_mass_idx" },
            { "fields": ["canonical.datasheet"], "name": "parts_canonical_datasheet_idx" },
            { "fields": ["canonical.approved"], "name": "parts_canonical_approved_idx" },
            { "fields": ["canonical.approved_by"], "name": "parts_canonical_approved_by_idx" },
            { "fields": ["file_groups"], "name": "parts_file_groups_idx" },
            { "fields": ["has_pdf"], "name": "parts_has_pdf_idx" },
            { "fields": ["has_png"], "name": "parts_has_png_idx" },
            { "fields": ["has_dxf"], "name": "parts_has_dxf_idx" },
            { "fields": ["has_step"], "name": "parts_has_step_idx" },
            { "fields": ["has_edr"], "name": "parts_has_edr_idx" },
            { "fields": ["has_3mf"], "name": "parts_has_3mf_idx" },
            { "fields": ["has_ply"], "name": "parts_has_ply_idx" },
            { "fields": ["has_stl"], "name": "parts_has_stl_idx" },
            { "fields": ["has_datasheet"], "name": "parts_has_datasheet_idx" },
        ],
        "db_alias": DB_ALIAS
    }

    @property
    def display_code(self) -> str:
        if self.revision:
            return f"{self.part_number}-{self.revision}"
        return self.part_number

    def save(self, *args, sync_materialized: bool = True, **kwargs):
        if sync_materialized:
            from app.services.part_materialized import sync_part_materialized_fields

            sync_part_materialized_fields(self)
        return super().save(*args, **kwargs)
