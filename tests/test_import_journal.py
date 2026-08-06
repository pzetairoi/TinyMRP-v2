"""Import journal and compensating-rollback tests (IMPORT-ATOMIC-01, Phase 4B).

Upload-pack import writes to two stores that cannot share a transaction:
MongoDB (parts, BOM links, file records) and the filesystem (deliverables).
`_commit_files` already rolls the filesystem back on failure, but the database
writes that ran before it did not, so a failure part-way through left changed
data behind with no record of what had landed.

These tests use fault injection to drive the failure paths directly, because
provoking a real cross-store failure is not reproducible.
"""

from __future__ import annotations

import mongomock
import pytest
from mongoengine import connect, disconnect

from app.models.import_journal import ImportJournal
from app.models.part import Part
from app.services import upload_pack
from app.services.timezone_utils import utc_now


@pytest.fixture()
def db():
    disconnect(alias="tinymrp-v2")
    connect(
        alias="tinymrp-v2",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
    )
    yield
    disconnect(alias="tinymrp-v2")


def _plan(pairs):
    """Minimal plan shaped like build_import_plan's output."""
    return {
        "parts": [
            {
                "part_number": pn,
                "revision": rev,
                "changed": True,
                "target_state": "new",
                "bom": {"action": "skip"},
                "files": [],
                "properties": {},
                "approval": {},
            }
            for pn, rev in pairs
        ],
        "_state": {"parts": {}, "managed": {}},
        "_parsed": {"links": []},
        "_config": {},
    }


# --- the journal exists and records the outcome ------------------------------


def test_successful_import_is_journalled_as_committed(db, monkeypatch):
    monkeypatch.setattr(upload_pack, "_write_boms", lambda plan: 0)
    monkeypatch.setattr(upload_pack, "_field_maps", lambda cfg: ({}, {}))
    monkeypatch.setattr(upload_pack, "_apply_properties", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "_apply_approval", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "sync_part_materialized_fields", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "upsert_part_files_detailed", lambda r: {"count": 0})

    result = upload_pack.execute_import_plan(_plan([("PN-1", "A")]))

    assert result["parts_created"] == 1
    assert result["operation_id"], "caller must receive an operation id"

    journal = ImportJournal.objects.get(operation_id=result["operation_id"])
    assert journal.status == "committed"
    assert journal.stage == "done"
    assert journal.parts_created == 1
    assert journal.finished_at is not None


def test_journal_is_written_before_effects_are_applied(db, monkeypatch):
    """A crash during the very first stage must still leave a record."""
    monkeypatch.setattr(upload_pack, "_field_maps", lambda cfg: ({}, {}))

    def _boom(*_a, **_k):
        raise RuntimeError("injected failure during properties")

    monkeypatch.setattr(upload_pack, "_apply_properties", _boom)

    with pytest.raises(RuntimeError, match="injected failure"):
        upload_pack.execute_import_plan(_plan([("PN-2", "A")]))

    journal = ImportJournal.objects.order_by("-started_at").first()
    assert journal is not None, "no journal entry was written before the failure"
    assert journal.status in {"failed", "rolled_back"}
    assert "injected failure" in journal.error


# --- the failure that motivated this phase -----------------------------------


def test_file_commit_failure_rolls_back_created_parts(db, monkeypatch):
    """The case IMPORT-ATOMIC-01 describes: DB written, then files fail.

    Before this change the part stayed in the database with no record. It must
    now be removed and the attempt recorded.
    """
    monkeypatch.setattr(upload_pack, "_field_maps", lambda cfg: ({}, {}))
    monkeypatch.setattr(upload_pack, "_apply_properties", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "_apply_approval", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "sync_part_materialized_fields", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "_write_boms", lambda plan: 0)

    def _fail_commit(*_a, **_k):
        raise RuntimeError("cross-store file commit failed")

    monkeypatch.setattr(upload_pack, "_commit_files", _fail_commit)

    with pytest.raises(RuntimeError, match="file commit failed"):
        upload_pack.execute_import_plan(_plan([("PN-3", "A")]))

    assert Part.objects(part_number="PN-3").count() == 0, (
        "a part created by a failed import must not survive"
    )

    journal = ImportJournal.objects.order_by("-started_at").first()
    assert journal.status == "rolled_back"
    assert any("PN-3" in action for action in journal.rollback_actions)


def test_rollback_does_not_delete_pre_existing_parts(db, monkeypatch):
    """Only parts this run created may be removed.

    A pre-existing part was overwritten in place; its prior values are not
    recoverable here, so deleting it would destroy data rather than restore it.
    It must be reported for manual reconciliation instead.
    """
    existing = Part(part_number="PN-OLD", revision="A", description="keep me", uom="EA")
    existing.save()

    plan = _plan([("PN-OLD", "A")])
    plan["_state"]["parts"] = {("PN-OLD", "A"): existing}
    plan["parts"][0]["target_state"] = "existing"

    monkeypatch.setattr(upload_pack, "_field_maps", lambda cfg: ({}, {}))
    monkeypatch.setattr(upload_pack, "_apply_properties", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "_apply_approval", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "sync_part_materialized_fields", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "_write_boms", lambda plan: 0)
    monkeypatch.setattr(
        upload_pack,
        "_commit_files",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("commit failed")),
    )

    with pytest.raises(RuntimeError):
        upload_pack.execute_import_plan(plan)

    assert Part.objects(part_number="PN-OLD").count() == 1, (
        "a pre-existing part must never be deleted by rollback"
    )

    journal = ImportJournal.objects.order_by("-started_at").first()
    assert journal.manual_followup, "in-place modification must be reported"
    assert any("PN-OLD" in note for note in journal.manual_followup)


def test_bom_write_failure_is_recorded_with_stage(db, monkeypatch):
    """The journal must say which stage failed, not just that it failed."""
    monkeypatch.setattr(upload_pack, "_field_maps", lambda cfg: ({}, {}))
    monkeypatch.setattr(upload_pack, "_apply_properties", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "_apply_approval", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "sync_part_materialized_fields", lambda *a, **k: None)

    def _fail_boms(*_a, **_k):
        raise RuntimeError("bom write exploded")

    monkeypatch.setattr(upload_pack, "_write_boms", _fail_boms)

    with pytest.raises(RuntimeError, match="bom write exploded"):
        upload_pack.execute_import_plan(_plan([("PN-4", "A")]))

    journal = ImportJournal.objects.order_by("-started_at").first()
    assert journal.stage == "boms", "the failing stage must be recorded"
    assert "bom write exploded" in journal.error


# --- operability -------------------------------------------------------------


def test_every_attempt_gets_a_unique_operation_id(db, monkeypatch):
    monkeypatch.setattr(upload_pack, "_write_boms", lambda plan: 0)
    monkeypatch.setattr(upload_pack, "_field_maps", lambda cfg: ({}, {}))
    monkeypatch.setattr(upload_pack, "_apply_properties", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "_apply_approval", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "sync_part_materialized_fields", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "upsert_part_files_detailed", lambda r: {"count": 0})

    first = upload_pack.execute_import_plan(_plan([("PN-5", "A")]))
    second = upload_pack.execute_import_plan(_plan([("PN-6", "A")]))

    assert first["operation_id"] != second["operation_id"]
    assert ImportJournal.objects.count() == 2


def test_touched_parts_are_recorded_for_reconciliation(db, monkeypatch):
    monkeypatch.setattr(upload_pack, "_write_boms", lambda plan: 0)
    monkeypatch.setattr(upload_pack, "_field_maps", lambda cfg: ({}, {}))
    monkeypatch.setattr(upload_pack, "_apply_properties", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "_apply_approval", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "sync_part_materialized_fields", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "upsert_part_files_detailed", lambda r: {"count": 0})

    result = upload_pack.execute_import_plan(_plan([("PN-7", "A"), ("PN-8", "B")]))
    journal = ImportJournal.objects.get(operation_id=result["operation_id"])

    recorded = {entry.split("\x1f")[0] for entry in journal.touched_parts}
    assert {"PN-7", "PN-8"} <= recorded


def test_journal_failure_does_not_break_the_import(db, monkeypatch):
    """Journalling is diagnostic; it must never be the reason an import fails."""
    monkeypatch.setattr(upload_pack, "_write_boms", lambda plan: 0)
    monkeypatch.setattr(upload_pack, "_field_maps", lambda cfg: ({}, {}))
    monkeypatch.setattr(upload_pack, "_apply_properties", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "_apply_approval", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "sync_part_materialized_fields", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "upsert_part_files_detailed", lambda r: {"count": 0})

    def _broken_journal(*_a, **_k):
        raise RuntimeError("journal collection unavailable")

    monkeypatch.setattr(ImportJournal, "save", _broken_journal)

    result = upload_pack.execute_import_plan(_plan([("PN-9", "A")]))

    assert result["parts_created"] == 1
    assert result["operation_id"] == "", "no id when the journal could not be written"


# --- idempotency (IMPORT-ATOMIC-01 residue) ----------------------------------


def _opts(**over):
    base = {
        "data_mode": "fill_blanks",
        "bom_mode": "fill_if_empty",
        "file_mode": "add_missing",
        "approval_mode": "preserve",
    }
    base.update(over)
    return base


def test_same_pack_and_policies_produce_the_same_key():
    key1 = upload_pack.import_idempotency_key(b"ZIPBYTES", _opts())
    key2 = upload_pack.import_idempotency_key(b"ZIPBYTES", _opts())
    assert key1 == key2


def test_different_content_produces_a_different_key():
    assert upload_pack.import_idempotency_key(b"A", _opts()) != (
        upload_pack.import_idempotency_key(b"B", _opts())
    )


def test_the_same_pack_under_different_policies_is_a_different_operation():
    """A fill-blanks run and a replace-all run touch different data.

    Treating them as the same operation would let a destructive re-import look
    like a harmless repeat.
    """
    fill = upload_pack.import_idempotency_key(b"ZIP", _opts(data_mode="fill_blanks"))
    replace = upload_pack.import_idempotency_key(b"ZIP", _opts(data_mode="replace_all"))
    assert fill != replace


def test_previous_successful_import_finds_only_committed_runs(db):
    key = "k1"
    ImportJournal(operation_id="op-failed", idempotency_key=key, status="failed").save()
    assert upload_pack.previous_successful_import(key) is None

    ImportJournal(
        operation_id="op-ok", idempotency_key=key, status="committed", finished_at=utc_now()
    ).save()
    found = upload_pack.previous_successful_import(key)
    assert found is not None and found.operation_id == "op-ok"


def test_previous_successful_import_ignores_a_rolled_back_run(db):
    # A rolled-back attempt SHOULD be retried; that is the point of retrying.
    ImportJournal(operation_id="op-rb", idempotency_key="k2", status="rolled_back").save()
    assert upload_pack.previous_successful_import("k2") is None


def test_previous_successful_import_tolerates_an_empty_key(db):
    assert upload_pack.previous_successful_import("") is None


def test_execute_records_the_key_on_the_journal(db, monkeypatch):
    monkeypatch.setattr(upload_pack, "_write_boms", lambda plan: 0)
    monkeypatch.setattr(upload_pack, "_field_maps", lambda cfg: ({}, {}))
    monkeypatch.setattr(upload_pack, "_apply_properties", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "_apply_approval", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "sync_part_materialized_fields", lambda *a, **k: None)
    monkeypatch.setattr(upload_pack, "upsert_part_files_detailed", lambda r: {"count": 0})

    result = upload_pack.execute_import_plan(_plan([("PN-K", "A")]), idempotency_key="abc123")
    journal = ImportJournal.objects.get(operation_id=result["operation_id"])
    assert journal.idempotency_key == "abc123"


# --- operator-facing view (IMPORT-ATOMIC-01 residue) -------------------------


def test_journal_row_exposes_what_reconciliation_needs(db):
    """A row that hides the failure reason cannot be reconciled."""
    from app.views.upload_pack import _journal_row

    entry = ImportJournal(
        operation_id="op-1",
        status="rolled_back",
        stage="files",
        uploaded_by="ops@example.com",
        parts_created=2,
        touched_parts=["PN-1\x1fA", "PN-2\x1fB"],
        rollback_actions=["deleted created part PN-1:A"],
        manual_followup=["pre-existing part PN-9 was modified in place"],
        error="RuntimeError: cross-store file commit failed",
    )
    entry.save()

    row = _journal_row(entry)
    assert row["status"] == "rolled_back"
    assert row["stage"] == "files"
    assert "cross-store" in row["error"]
    assert row["rollback_actions"] == ["deleted created part PN-1:A"]
    assert row["manual_followup"]
    # The \x1f separator is an internal storage detail, not something to show.
    assert row["touched_parts"] == ["PN-1:A", "PN-2:B"]


def test_journal_endpoints_are_registered(db, monkeypatch):
    """The journal is only reconcilable if it is actually reachable."""
    import app as app_module

    monkeypatch.setenv("SECRET_KEY", "journal-test-key")
    monkeypatch.setenv("SECURITY_PASSWORD_SALT", "journal-test-salt")
    app_module.init_mongo = lambda _app: None
    app = app_module.create_app()

    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/import/operations" in rules
    assert "/api/import/operations/<operation_id>" in rules
