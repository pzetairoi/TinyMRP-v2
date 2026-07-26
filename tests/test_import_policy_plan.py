import io
import json
import zipfile

import pytest

from app.models.artifact import PartFile
from app.models.bom import BOMLink
from app.models.extra_file import PartExtraFile
from app.models.part import Part
from app.services.field_config import save_field_config
from app.services.upload_pack import ImportPermissionError, import_upload_pack


PREVIEW = {"imports.preview"}
LOW = PREVIEW | {"imports.execute_low_risk"}
MANAGER = LOW | {"imports.execute_approved", "imports.override_approved"}


def _pack(rows, tree_rows=None, files=None):
    tree_rows = tree_rows or [
        ("1", rows[0]["partnumber"], rows[0].get("revision", ""), 1),
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("POLICY_FLATBOM.txt", "\n".join(json.dumps(row) for row in rows))
        archive.writestr(
            "POLICY_TREEBOM.txt",
            "ITEM NO.\tPART NUMBER\tRevision\tQTY.\n"
            + "\n".join("\t".join(map(str, row)) for row in tree_rows),
        )
        for name, content in (files or {}).items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _run(data, *, dry_run=True, permissions=MANAGER, **options):
    return import_upload_pack(
        data,
        "policy.zip",
        dry_run=dry_run,
        actor_permissions=set(permissions),
        scan_artifacts=False,
        generate_thumbs=False,
        **options,
    )


def test_preview_is_no_write_single_parse_and_batched_state_load(app):
    data = _pack(
        [{"partnumber": "PLAN-NEW", "revision": "A", "material": "Steel"}],
        files={"deliverables/pdf/PLAN-NEW_REV_A.pdf": b"pdf"},
    )

    result = _run(
        data,
        permissions=LOW,
        data_mode="fill_blanks",
        bom_mode="fill_if_empty",
        file_mode="add_missing",
        approval_mode="preserve",
    )

    assert result["required_permissions"] == ["imports.execute_low_risk"]
    assert result["allowed"] is True
    assert result["diagnostics"] == {
        "query_count": 4,
        "zip_open_count": 1,
        "flatbom_parse_count": 1,
        "treebom_parse_count": 1,
        "storage_scan_fallback": False,
        "materialized_part_saves": 0,
    }
    assert Part.objects(part_number="PLAN-NEW", revision="A").first() is None
    assert PartFile.objects(part_number="PLAN-NEW", revision="A").count() == 0


def test_property_replacement_uses_advanced_permission_and_apply_keeps_redline(app):
    Part(
        part_number="PLAN-DRAFT",
        revision="A",
        description="Before",
        attrs={"material": "Steel"},
    ).save()
    data = _pack(
        [
            {
                "partnumber": "PLAN-DRAFT",
                "revision": "A",
                "description": "After",
                "material": "Aluminium",
            }
        ]
    )
    preview = _run(data, data_mode="replace_unapproved")
    entry = preview["plan"]["parts"][0]

    assert preview["required_permissions"] == ["imports.execute_approved"]
    assert {item["action"] for item in entry["properties"]} >= {"replace"}
    with pytest.raises(ImportPermissionError):
        _run(data, dry_run=False, permissions=LOW, data_mode="replace_unapproved")

    applied = _run(data, dry_run=False, data_mode="replace_unapproved")
    assert applied["plan"]["parts"] == preview["plan"]["parts"]
    part = Part.objects.get(part_number="PLAN-DRAFT", revision="A")
    assert part.description == "After"
    assert part.attrs["material"] == "Aluminium"
    assert applied["diagnostics"]["materialized_part_saves"] == 1


def test_any_approved_target_mutation_requires_both_advanced_capabilities(app, tmp_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    Part(
        part_number="PLAN-APPROVED",
        revision="A",
        description="",
        attrs={"approved_by": "QA"},
    ).save()
    data = _pack(
        [{"partnumber": "PLAN-APPROVED", "revision": "A", "description": "Filled"}],
        files={"extra/PLAN-APPROVED/A/report.txt": b"report"},
    )
    preview = _run(
        data,
        permissions=LOW,
        data_mode="fill_blanks",
        file_mode="add_missing",
    )

    assert preview["required_permissions"] == [
        "imports.execute_approved",
        "imports.override_approved",
    ]
    assert preview["missing_permissions"] == [
        "imports.execute_approved",
        "imports.override_approved",
    ]
    assert preview["plan"]["parts"][0]["target_state"] == "existing_approved"
    with pytest.raises(ImportPermissionError):
        _run(data, dry_run=False, permissions={"imports.override_approved"})


def test_bom_modes_are_independent_and_show_add_remove_quantity_redline(app):
    Part(part_number="PLAN-PARENT", revision="A").save()
    BOMLink(
        parent_pn="PLAN-PARENT",
        parent_rev="A",
        child_pn="OLD",
        child_rev="A",
        qty=2,
    ).save()
    data = _pack(
        [
            {"partnumber": "PLAN-PARENT", "revision": "A"},
            {"partnumber": "NEW", "revision": "B"},
        ],
        [
            ("1", "PLAN-PARENT", "A", 1),
            ("1.1", "NEW", "B", 3),
        ],
    )

    skipped = _run(data, data_mode="skip", bom_mode="fill_if_empty")
    assert skipped["plan"]["parts"][1]["bom"]["action"] == "skipped"
    replaced = _run(data, data_mode="skip", bom_mode="replace_unapproved")
    parent = next(
        item for item in replaced["plan"]["parts"] if item["part_number"] == "PLAN-PARENT"
    )
    planned = {item.get("planned_action", item["action"]) for item in parent["bom"]["changes"]}
    assert planned == {"add", "remove"}
    assert replaced["required_permissions"] == [
        "imports.execute_low_risk",
        "imports.execute_approved",
    ]


def test_managed_and_associated_files_share_collision_policy(app, tmp_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    part = Part(part_number="PLAN-FILES", revision="A").save()
    managed_path = tmp_path / "pdf" / "PLAN-FILES_REV_A.pdf"
    managed_path.parent.mkdir()
    managed_path.write_bytes(b"old")
    PartFile(
        part_number=part.part_number,
        revision=part.revision,
        ext_group="pdf",
        ext="pdf",
        is_dwg=False,
        rel_path="pdf/PLAN-FILES_REV_A.pdf",
        path=str(managed_path),
        sha256="old",
    ).save()
    extra_path = tmp_path / "extra" / "PLAN-FILES" / "A" / "report.txt"
    extra_path.parent.mkdir(parents=True)
    extra_path.write_bytes(b"old")
    PartExtraFile(
        part_number=part.part_number,
        revision=part.revision,
        original_name="report.txt",
        rel_path="extra/PLAN-FILES/A/report.txt",
        sha256="old",
    ).save()
    data = _pack(
        [{"partnumber": "PLAN-FILES", "revision": "A"}],
        files={
            "deliverables/pdf/PLAN-FILES_REV_A.pdf": b"new",
            "extra/PLAN-FILES/A/report.txt": b"new",
        },
    )

    add_only = _run(data, data_mode="skip", file_mode="add_missing")
    assert {item["action"] for item in add_only["plan"]["parts"][0]["files"]} == {
        "skipped"
    }
    replace = _run(data, data_mode="skip", file_mode="replace_unapproved")
    assert {item["action"] for item in replace["plan"]["parts"][0]["files"]} == {
        "replace"
    }
    assert replace["required_permissions"] == ["imports.execute_approved"]


def test_configured_custom_field_and_approval_aliases_are_logical_redline_fields(app):
    save_field_config(
        {
            "custom_fields": [
                {
                    "id": "inspection_grade",
                    "label": "Inspection Grade",
                    "data_type": "text",
                    "source_path": "attrs.QA_Grade",
                }
            ],
            "canonical_aliases": [
                {
                    "field_id": "approved_by",
                    "aliases": ["approved_by", "EngineeringApproval"],
                }
            ],
        }
    )
    data = _pack(
        [
            {
                "partnumber": "PLAN-ALIASES",
                "revision": "A",
                "QA_Grade": "A1",
                "EngineeringApproval": "QA Person",
            }
        ]
    )
    result = _run(data, data_mode="fill_blanks", approval_mode="preserve")
    entry = result["plan"]["parts"][0]

    custom = next(item for item in entry["properties"] if item["field_id"] == "inspection_grade")
    assert custom["label"] == "Inspection Grade"
    assert custom["source_key"] == "QA_Grade"
    assert next(item for item in entry["approval"] if item["field_id"] == "approved_by")[
        "after"
    ] == "QA Person"


def test_conflicting_approval_aliases_are_conservative_and_visible(app):
    data = _pack(
        [
            {
                "partnumber": "PLAN-CONFLICT",
                "revision": "A",
                "approved": "Approved",
                "is_approved": "Not Approved",
            }
        ]
    )
    result = _run(data, approval_mode="replace_all")
    entry = result["plan"]["parts"][0]

    assert result["plan"]["approval_integrity_warnings"] == 1
    assert all(item["action"] == "blocked" for item in entry["approval"])
    assert entry["target_state"] == "new"
    assert entry["blocked"] is True


@pytest.mark.parametrize(
    ("legacy", "expected"),
    [
        (
            "preserve",
            ("fill_blanks", "fill_if_empty", "add_missing", "preserve"),
        ),
        (
            "unless_existing_approved",
            (
                "replace_unapproved",
                "replace_unapproved",
                "replace_unapproved",
                "preserve",
            ),
        ),
        ("always", ("replace_all", "replace_all", "replace_all", "replace_all")),
    ],
)
def test_legacy_override_translation_remains_visible(app, legacy, expected):
    result = _run(
        _pack([{"partnumber": f"LEGACY-{legacy}", "revision": "A"}]),
        override_mode=legacy,
    )
    options = result["options"]
    assert (
        options["data_mode"],
        options["bom_mode"],
        options["file_mode"],
        options["approval_mode"],
    ) == expected
