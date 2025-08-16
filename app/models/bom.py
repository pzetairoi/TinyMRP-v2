from mongoengine import Document, StringField, ReferenceField, FloatField, ListField, DateTimeField, BooleanField
from datetime import datetime
from .part import Part

class BOMLink(Document):
    # Store PNs as strings so we can show BOM even if child Part not created yet
    parent_pn   = StringField(required=True)       # e.g. "ASM-1001"
    child_pn    = StringField(required=True)       # e.g. "CMP-2002"
    qty         = FloatField(default=1.0)
    uom         = StringField(default="EA")
    refdes      = ListField(StringField())         # e.g. ["R1","R2"] for PCB, or position notes
    scrap_rate  = FloatField(default=0.0)          # percentage 0..1
    alt_group   = StringField(default="")          # optional alternates group token
    effective_from = DateTimeField()
    effective_to   = DateTimeField()
    phantom     = BooleanField(default=False)      # pass-through BOM (if you use that concept)
    updated_at  = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "bom_links",
        "indexes": [
            "parent_pn", "child_pn",
            {"fields": ["parent_pn", "child_pn"], "unique": False},
        ],
    }

    # Convenience lookups (safe if Part missing)
    @property
    def parent(self):
        return Part.objects(part_number=self.parent_pn).first()

    @property
    def child(self):
        return Part.objects(part_number=self.child_pn).first()
