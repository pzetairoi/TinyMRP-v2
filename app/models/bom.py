# app/models/bom.py
from mongoengine import Document, StringField, FloatField, ListField, DateTimeField, BooleanField
from datetime import datetime
from app.models.part import Part  # <-- absolute import

DB_ALIAS = "tinymrp-v2"

class BOMLink(Document):
    parent_pn   = StringField(required=True)
    child_pn    = StringField(required=True)
    qty         = FloatField(default=1.0)
    uom         = StringField(default="EA")
    refdes      = ListField(StringField())
    scrap_rate  = FloatField(default=0.0)
    alt_group   = StringField(default="")
    effective_from = DateTimeField()
    effective_to   = DateTimeField()
    phantom     = BooleanField(default=False)
    updated_at  = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "bom",
        "indexes": ["parent_pn", "child_pn", ("parent_pn", "child_pn")],
        "db_alias": DB_ALIAS
    }

    @property
    def parent(self):
        return Part.objects(part_number=self.parent_pn).first()

    @property
    def child(self):
        return Part.objects(part_number=self.child_pn).first()
