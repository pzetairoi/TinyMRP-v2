"""Selective purge must delete exactly what was asked, and nothing more."""
import uuid

from app.models.auth import Role, User
from app.models.bom import BOMLink
from app.models.part import Part
from app.models.part_annotation import PartAnnotation
from app.services import purge
from app.services.authorization import has_permission
from app.services.standard_roles import STANDARD_ROLES


def _role(name):
    existing = Role.objects(name=name).first()
    if existing:
        return existing
    return Role(name=name, permissions=list(STANDARD_ROLES[name].permissions)).save()


def _user(email, *roles):
    return User(email=email, password="t", active=True,
                fs_uniquifier=str(uuid.uuid4()), roles=list(roles)).save()


def test_only_selected_targets_are_deleted(app):
    with app.app_context():
        Part.objects.delete(); BOMLink.objects.delete(); PartAnnotation.objects.delete()
        Part(part_number="PURGE-1", revision="A", description="d").save()
        BOMLink(parent_pn="PURGE-1", parent_rev="A", child_pn="PURGE-2",
                child_rev="A", qty=1).save()
        PartAnnotation(part_number="PURGE-1", revision="A", notes="keep me").save()

        admin = _user("purge-admin@t.test", _role("administrator"))
        results = purge.run(["bom"], admin, has_permission)

        assert results == {"bom": 1}
        assert BOMLink.objects.count() == 0
        # Untouched targets survive.
        assert Part.objects.count() == 1
        assert PartAnnotation.objects.count() == 1


def test_purging_properties_keeps_the_part_entry(app):
    with app.app_context():
        Part.objects.delete()
        Part(part_number="PURGE-P", revision="A", description="d",
             attrs={"material": "Steel"}).save()

        admin = _user("purge-props@t.test", _role("administrator"))
        purge.run(["part_properties"], admin, has_permission, confirmation="DELETE")

        part = Part.objects.get(part_number="PURGE-P")
        assert part.attrs == {}
        assert part.part_number == "PURGE-P"


def test_admins_are_never_deleted_by_the_user_purge(app):
    with app.app_context():
        User.objects.delete()
        admin = _user("purge-keep-admin@t.test", _role("administrator"))
        victim = _user("purge-drop@t.test", _role("engineering"))

        purge.run(["users"], admin, has_permission, confirmation="DELETE")

        assert User.objects(id=admin.id).first() is not None
        assert User.objects(id=victim.id).first() is None


def test_targets_without_permission_are_skipped(app):
    with app.app_context():
        Part.objects.delete()
        Part(part_number="PURGE-DENY", revision="A", description="d").save()
        # Engineering has no parts.purge, so the target must be refused.
        engineer = _user("purge-eng@t.test", _role("engineering"))

        assert purge.run(["parts"], engineer, has_permission, confirmation="DELETE") == {}
        assert Part.objects.count() == 1
        assert not [row for row in purge.available(engineer, has_permission)
                    if row["key"] == "parts"]


def test_custom_roles_purge_demotes_users_to_minimum_access(app):
    """Deleting custom roles must not leave accounts with no role at all."""
    with app.app_context():
        User.objects.delete()
        Role.objects(name__nin=["administrator", "internal", "engineering"]).delete()
        _role("internal")
        custom = Role(name="bespoke-role", permissions=["parts.read"]).save()

        admin = _user("roles-admin@t.test", _role("administrator"))
        only_custom = _user("roles-only@t.test", custom)
        also_standard = _user("roles-both@t.test", custom, _role("engineering"))

        removed = purge.run(["custom_roles"], admin, has_permission, confirmation="DELETE")
        assert removed == {"custom_roles": 1}
        assert Role.objects(name="bespoke-role").first() is None

        # Left with nothing -> demoted to the minimum general role.
        only_custom.reload()
        assert [r.name for r in only_custom.roles] == ["internal"]

        # Still had a standard role -> keeps exactly that, no fallback added.
        also_standard.reload()
        assert [r.name for r in also_standard.roles] == ["engineering"]

        # Standard roles are never removed.
        assert Role.objects(name="administrator").first() is not None


def test_purging_comments_clears_pending_review_flags(app):
    """A purged comment must not leave the part in the pending-review filter.

    The grid filters on the materialized counter in Mongo (which is what keeps
    the inventory fast), so the counter has to be cleared with the source data.
    """
    with app.app_context():
        Part.objects.delete(); PartAnnotation.objects.delete()
        part = Part(part_number="REVIEW-1", revision="A", description="d",
                    pending_review_count=2, pending_review_severity="high").save()
        PartAnnotation(part_number="REVIEW-1", revision="A",
                       comments=[{"text": "fix", "status": "open", "priority": "high"}]).save()

        admin = _user("review-admin@t.test", _role("administrator"))
        purge.run(["annotations"], admin, has_permission, confirmation="DELETE")

        part.reload()
        assert part.pending_review_count == 0
        assert part.pending_review_severity == ""
        # And the grid filter no longer matches it.
        assert Part.objects(pending_review_count__gt=0).count() == 0


def test_irreversible_targets_refuse_to_run_without_the_typed_phrase(app):
    """The guard lives in the service, so posting the form directly cannot skip it."""
    with app.app_context():
        Part.objects.delete()
        Part(part_number="CONFIRM-1", revision="A", description="d").save()
        admin = _user("confirm-admin@t.test", _role("administrator"))

        assert purge.requires_confirmation(["parts"]) == ["Part entries"]
        # No phrase, and a wrong phrase, both refuse.
        assert purge.run(["parts"], admin, has_permission) == {}
        assert purge.run(["parts"], admin, has_permission, confirmation="delete") == {}
        assert Part.objects.count() == 1

        # The exact phrase lets it through.
        assert purge.run(["parts"], admin, has_permission, confirmation="DELETE") == {"parts": 1}
        assert Part.objects.count() == 0


def test_reversible_targets_do_not_need_confirmation(app):
    """File records rebuild from a rescan, so they stay a single click."""
    with app.app_context():
        from app.models.artifact import PartFile

        PartFile.objects.delete()
        PartFile(part_number="CONF-F", revision="A", ext_group="pdf", ext="pdf",
                 rel_path="pdf/x.pdf", path="/tmp/conf-f.pdf").save()
        admin = _user("confirm-rev@t.test", _role("administrator"))

        assert purge.requires_confirmation(["part_files"]) == []
        assert purge.run(["part_files"], admin, has_permission) == {"part_files": 1}


def test_mixed_selection_still_runs_the_reversible_half(app):
    """A missing phrase blocks only the irreversible targets, not the batch."""
    with app.app_context():
        from app.models.artifact import PartFile

        Part.objects.delete(); PartFile.objects.delete()
        Part(part_number="MIX-1", revision="A", description="d").save()
        PartFile(part_number="MIX-1", revision="A", ext_group="pdf", ext="pdf",
                 rel_path="pdf/m.pdf", path="/tmp/mix.pdf").save()
        admin = _user("confirm-mix@t.test", _role("administrator"))

        results = purge.run(["parts", "part_files"], admin, has_permission)

        assert results == {"part_files": 1}
        assert Part.objects.count() == 1
