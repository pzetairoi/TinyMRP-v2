from mongoengine import (
    DateTimeField,
    DictField,
    Document,
    EmbeddedDocument,
    EmbeddedDocumentListField,
    IntField,
    ListField,
    StringField,
)

from app.services.timezone_utils import utc_now


DB_ALIAS = "tinymrp-v2"

THREAD_PRIORITIES = ("low", "normal", "high")
THREAD_STATUSES = ("open", "resolved")


class PartDrawingMarkupMessage(EmbeddedDocument):
    id = StringField(required=True)
    author = StringField(default="")
    ts = DateTimeField(default=utc_now)
    text = StringField(default="")


class PartDrawingMarkupThread(EmbeddedDocument):
    id = StringField(required=True)
    object_ids = ListField(StringField(), default=list)
    title = StringField(default="")
    priority = StringField(default="normal", choices=THREAD_PRIORITIES)
    status = StringField(default="open", choices=THREAD_STATUSES)

    created_by = StringField(default="")
    created_at = DateTimeField(default=utc_now)
    updated_by = StringField(default="")
    updated_at = DateTimeField(default=utc_now)

    resolved_by = StringField(default="")
    resolved_at = DateTimeField()

    messages = EmbeddedDocumentListField(PartDrawingMarkupMessage, default=list)


class PartDrawingMarkup(Document):
    """Vector markup layer drawn over an exported drawing PNG.

    Identity includes the source fingerprint on purpose: when the drawing
    file changes, the old layer is kept as history and a new layer is
    created for the new drawing content.
    """

    part_number = StringField(required=True)
    revision = StringField(default="")

    source_file_id = StringField(required=True)   # PartFile id (string form)
    source_rel_path = StringField(default="")
    source_fingerprint = StringField(required=True)
    page_number = IntField(default=1)

    canvas_schema_version = IntField(default=1)
    canvas_json = DictField(default=dict)

    threads = EmbeddedDocumentListField(PartDrawingMarkupThread, default=list)
    version = IntField(default=0)

    created_by = StringField(default="")
    created_at = DateTimeField(default=utc_now)
    updated_by = StringField(default="")
    updated_at = DateTimeField(default=utc_now)

    meta = {
        "collection": "part_drawing_markups",
        "db_alias": DB_ALIAS,
        "indexes": [
            {
                "fields": [
                    "part_number",
                    "revision",
                    "source_file_id",
                    "source_fingerprint",
                    "page_number",
                ],
                "unique": True,
                "name": "unique_part_drawing_markup_source",
            },
            {"fields": ["part_number", "revision"], "name": "part_drawing_markup_part_rev_idx"},
            {"fields": ["updated_at"], "name": "part_drawing_markup_updated_at_idx"},
            {"fields": ["threads.status"], "name": "part_drawing_markup_thread_status_idx"},
        ],
    }
