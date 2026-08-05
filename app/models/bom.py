# app/models/bom.py
from mongoengine import Document, StringField, FloatField, ListField, DateTimeField, BooleanField, DictField
from app.models.part import Part  # <-- absolute import
from app.services.timezone_utils import utc_now

DB_ALIAS = "tinymrp-v2"

class BOMLink(Document):
    parent_pn   = StringField(required=True)
    parent_rev  = StringField(default="")  # new: parent revision
    child_pn    = StringField(required=True)
    child_rev   = StringField(default="")  # new: child revision
    qty         = FloatField(default=1.0)
    uom         = StringField(default="EA")
    refdes      = ListField(StringField())
    occurrences = ListField(DictField(), default=list)
    scrap_rate  = FloatField(default=0.0)
    alt_group   = StringField(default="")
    effective_from = DateTimeField()
    effective_to   = DateTimeField()
    phantom     = BooleanField(default=False)
    updated_at  = DateTimeField(default=utc_now)

    meta = {
        "collection": "bom",
        "indexes": [
            "parent_pn",
            "child_pn",
            ("parent_pn", "child_pn"),
            ("parent_pn", "parent_rev", "child_pn", "child_rev"),
        ],
        "db_alias": DB_ALIAS
    }

    @property
    def parent(self):
        return Part.objects(part_number=self.parent_pn, revision=(self.parent_rev or "")).first()

    @property
    def child(self):
        return Part.objects(part_number=self.child_pn, revision=(self.child_rev or "")).first()
