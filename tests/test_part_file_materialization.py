import pytest

from app.models.artifact import PartFile
from app.models.part import Part
from app.services.field_config import context_field_ids, get_field_config
from app.services.part_materialized import rebuild_part_materialized_fields


FILE_FLAG_CASES = [
    ("pdf", "pdf", "has_pdf"),
    ("png", "png", "has_png"),
    ("dxf", "dxf", "has_dxf"),
    ("step", "step", "has_step"),
    ("edr", "eprt", "has_edr"),
    ("3mf", "3mf", "has_3mf"),
    ("ply", "ply", "has_ply"),
    ("stl", "stl", "has_stl"),
    ("datasheet", "pdf", "has_datasheet"),
]


def _file(part: Part, group: str, ext: str) -> PartFile:
    return PartFile(
        part_number=part.part_number,
        revision=part.revision,
        ext_group=group,
        ext=ext,
        rel_path=f"{group}/{part.part_number}.{ext}",
        path=f"C:/vault/{group}/{part.part_number}.{ext}",
    )


@pytest.mark.parametrize(("group", "ext", "flag_field"), FILE_FLAG_CASES)
def test_direct_part_file_add_and_remove_updates_materialized_flag(app, group, ext, flag_field):
    part = Part(part_number=f"FLAG-{group.upper()}", revision="A").save()
    artifact = _file(part, group, ext).save()

    part.reload()
    assert getattr(part, flag_field) is True

    artifact.delete()
    part.reload()
    assert getattr(part, flag_field) is False


def test_datasheet_attribute_sets_materialized_datasheet_flag(app):
    part = Part(
        part_number="FLAG-DATASHEET-ATTR",
        revision="A",
        attrs={"datasheet": "vendor-specification.pdf"},
    ).save()

    part.reload()
    assert part.has_datasheet is True


def test_rebuild_repairs_stale_file_flags(app):
    part = Part(part_number="FLAG-REBUILD", revision="A").save()
    _file(part, "pdf", "pdf").save()
    Part.objects(id=part.id).update(set__has_pdf=False, set__file_groups=[])

    report = rebuild_part_materialized_fields()

    part.reload()
    assert report["errors"] == 0
    assert report["updated"] >= 1
    assert part.has_pdf is True
    assert "pdf" in part.file_groups


def test_all_file_boolean_indexes_are_declared():
    index_names = {
        spec.get("name")
        for spec in Part._meta.get("index_specs", [])
        if isinstance(spec, dict)
    }
    assert {
        "parts_has_pdf_idx",
        "parts_has_png_idx",
        "parts_has_dxf_idx",
        "parts_has_step_idx",
        "parts_has_edr_idx",
        "parts_has_3mf_idx",
        "parts_has_ply_idx",
        "parts_has_stl_idx",
        "parts_has_datasheet_idx",
    }.issubset(index_names)


def test_parts_field_configuration_exposes_file_and_approval_booleans(app):
    available = set(context_field_ids("parts_list", get_field_config()))
    assert {
        "approved",
        "has_pdf",
        "has_png",
        "has_dxf",
        "has_step",
        "has_edr",
        "has_3mf",
        "has_ply",
        "has_stl",
        "has_datasheet",
    }.issubset(available)
