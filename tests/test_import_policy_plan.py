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
RESOURCE_WRITES = {
    "parts.create",
    "parts.update",
    "bom.update",
    "files.add",
    "files.replace",
}
LOW = PREVIEW | {"imports.execute_low_risk"} | RESOURCE_WRITES
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

    assert result["required_permissions"] == [
        "files.add",
        "imports.execute_low_risk",
        "parts.create",
    ]
    assert result["allowed"] is True
    diagnostics = result["diagnostics"]
    assert diagnostics["query_count"] == 4
    assert diagnostics["zip_open_count"] == 1
    assert diagnostics["flatbom_parse_count"] == 1
    assert diagnostics["treebom_parse_count"] == 1
    assert diagnostics["materialized_part_saves"] == 0
    assert "storage_scan_fallback" not in diagnostics
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

    assert preview["required_permissions"] == [
        "imports.execute_approved",
        "parts.update",
    ]
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
        "files.add",
        "imports.execute_approved",
        "imports.override_approved",
        "parts.update",
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
        "bom.update",
        "imports.execute_approved",
        "imports.execute_low_risk",
        "parts.create",
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
    assert replace["required_permissions"] == [
        "files.replace",
        "imports.execute_approved",
    ]


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


def test_default_policies_are_fill_only_and_invalid_modes_are_rejected(app):
    result = _run(_pack([{"partnumber": "PLAN-DEFAULTS", "revision": "A"}]))
    assert result["options"] == {
        "data_mode": "fill_blanks",
        "bom_mode": "fill_if_empty",
        "file_mode": "add_missing",
        "approval_mode": "preserve",
    }
    with pytest.raises(ValueError, match="invalid data_mode"):
        _run(_pack([{"partnumber": "PLAN-BAD", "revision": "A"}]), data_mode="always")


def test_blank_revision_targets_are_exact(app):
    Part(part_number="PLAN-BLANK", revision="", description="Existing").save()
    Part(part_number="PLAN-BLANK", revision="B", description="Other rev").save()
    data = _pack(
        [{"partnumber": "PLAN-BLANK", "revision": "", "material": "Steel"}],
        [("1", "PLAN-BLANK", "", 1)],
    )

    applied = _run(data, dry_run=False, data_mode="fill_blanks")

    assert [
        (item["part_number"], item["revision"]) for item in applied["plan"]["parts"]
    ] == [("PLAN-BLANK", "")]
    blank = Part.objects.get(part_number="PLAN-BLANK", revision="")
    other = Part.objects.get(part_number="PLAN-BLANK", revision="B")
    assert blank.attrs.get("material") == "Steel"
    assert other.attrs.get("material") is None


def test_duplicate_equal_aliases_consolidate_and_conflicts_block(app):
    equal = _run(
        _pack(
            [
                {
                    "partnumber": "PLAN-DUP-EQ",
                    "revision": "A",
                    "material": "Steel",
                    "Material": "Steel",
                }
            ]
        )
    )
    material = next(
        item
        for item in equal["plan"]["parts"][0]["properties"]
        if item["field_id"] == "material"
    )
    assert material["action"] == "add"
    assert material["after"] == "Steel"

    conflict = _run(
        _pack(
            [
                {
                    "partnumber": "PLAN-DUP-NE",
                    "revision": "A",
                    "material": "Steel",
                    "Material": "Aluminium",
                }
            ]
        )
    )
    conflicted = next(
        item
        for item in conflict["plan"]["parts"][0]["properties"]
        if item["field_id"] == "material"
    )
    assert conflicted["after"] == "Steel"
    assert list(conflicted.get("alias_conflicts") or {}) == ["Material"]
    assert "Conflicting duplicate aliases" in conflicted["reason"]


def test_empty_parent_bom_fill_and_approved_bom_replacement(app):
    Part(part_number="PLAN-EMPTY-PARENT", revision="A").save()
    fill_data = _pack(
        [
            {"partnumber": "PLAN-EMPTY-PARENT", "revision": "A"},
            {"partnumber": "PLAN-CHILD", "revision": "A"},
        ],
        [
            ("1", "PLAN-EMPTY-PARENT", "A", 1),
            ("1.1", "PLAN-CHILD", "A", 4),
        ],
    )
    applied = _run(fill_data, dry_run=False, bom_mode="fill_if_empty")
    parent = next(
        item
        for item in applied["plan"]["parts"]
        if item["part_number"] == "PLAN-EMPTY-PARENT"
    )
    assert parent["bom"]["action"] == "add"
    links = list(BOMLink.objects(parent_pn="PLAN-EMPTY-PARENT", parent_rev="A"))
    assert [(link.child_pn, link.child_rev, link.qty) for link in links] == [
        ("PLAN-CHILD", "A", 4.0)
    ]

    Part(
        part_number="PLAN-APPROVED-BOM",
        revision="A",
        attrs={"approved_by": "QA"},
    ).save()
    BOMLink(
        parent_pn="PLAN-APPROVED-BOM",
        parent_rev="A",
        child_pn="OLD",
        child_rev="A",
        qty=1,
    ).save()
    replace_data = _pack(
        [
            {"partnumber": "PLAN-APPROVED-BOM", "revision": "A"},
            {"partnumber": "PLAN-CHILD", "revision": "A"},
        ],
        [
            ("1", "PLAN-APPROVED-BOM", "A", 1),
            ("1.1", "PLAN-CHILD", "A", 2),
        ],
    )
    blocked = _run(replace_data, bom_mode="replace_unapproved", data_mode="skip")
    approved_entry = next(
        item
        for item in blocked["plan"]["parts"]
        if item["part_number"] == "PLAN-APPROVED-BOM"
    )
    assert approved_entry["bom"]["action"] == "blocked"

    with pytest.raises(ImportPermissionError):
        _run(
            replace_data,
            dry_run=False,
            permissions=LOW,
            bom_mode="replace_all",
            data_mode="skip",
        )
    allowed = _run(replace_data, dry_run=False, bom_mode="replace_all", data_mode="skip")
    entry = next(
        item
        for item in allowed["plan"]["parts"]
        if item["part_number"] == "PLAN-APPROVED-BOM"
    )
    assert entry["bom"]["action"] == "replace"
    links = list(BOMLink.objects(parent_pn="PLAN-APPROVED-BOM", parent_rev="A"))
    assert [(link.child_pn, link.child_rev) for link in links] == [("PLAN-CHILD", "A")]


def test_bom_only_package_discovers_existing_storage_files_for_all_parts(app, tmp_path):
    app.config["FILE_SOURCES"] = [
        {"local_root": str(tmp_path), "url_prefix": "/deliverables"}
    ]
    (tmp_path / "pdf").mkdir()
    (tmp_path / "pdf" / "PLAN-NO-FILES_REV_A.pdf").write_bytes(b"root pdf")
    (tmp_path / "pdf" / "PLAN-NO-FILES-CHILD_REV_A.pdf").write_bytes(b"child pdf")
    data = _pack(
        [
            {"partnumber": "PLAN-NO-FILES", "revision": "A", "material": "Steel"},
            {"partnumber": "PLAN-NO-FILES-CHILD", "revision": "A"},
        ],
        [
            ("1", "PLAN-NO-FILES", "A", 1),
            ("1.1", "PLAN-NO-FILES-CHILD", "A", 2),
        ],
    )

    with app.app_context():
        applied = _run(data, dry_run=False)

    assert applied["metrics"]["files_written"] == 0
    assert applied["metrics"]["files_discovered"] == 2
    assert PartFile.objects(part_number="PLAN-NO-FILES", ext_group="pdf").count() == 1
    assert PartFile.objects(part_number="PLAN-NO-FILES-CHILD", ext_group="pdf").count() == 1
    assert PartExtraFile.objects(part_number="PLAN-NO-FILES").count() == 0
    part = Part.objects.get(part_number="PLAN-NO-FILES", revision="A")
    assert part.attrs.get("material") == "Steel"
    links = list(BOMLink.objects(parent_pn="PLAN-NO-FILES", parent_rev="A"))
    assert [(link.child_pn, link.qty) for link in links] == [
        ("PLAN-NO-FILES-CHILD", 2.0)
    ]

    # Re-importing the identical pack changes no part data, yet still
    # reconciles file records against storage.
    (tmp_path / "step").mkdir()
    (tmp_path / "step" / "PLAN-NO-FILES-CHILD_REV_A.step").write_bytes(b"child step")
    with app.app_context():
        reapplied = _run(data, dry_run=False)
    assert reapplied["metrics"]["parts_created"] == 0
    assert reapplied["metrics"]["parts_updated"] == 0
    assert reapplied["metrics"]["files_discovered"] >= 1
    assert (
        PartFile.objects(part_number="PLAN-NO-FILES-CHILD", ext_group="step").count()
        == 1
    )


def test_scope_check_blocks_out_of_scope_existing_targets(app):
    Part(part_number="PLAN-SCOPED", revision="A", description="Existing").save()
    data = _pack(
        [
            {
                "partnumber": "PLAN-SCOPED",
                "revision": "A",
                "description": "Replacement",
            }
        ]
    )

    from app.services.upload_pack import ImportScopeError

    with pytest.raises(ImportScopeError):
        _run(
            data,
            dry_run=False,
            data_mode="replace_unapproved",
            scope_check=lambda pairs: list(pairs),
        )
    part = Part.objects.get(part_number="PLAN-SCOPED", revision="A")
    assert part.description == "Existing"


def test_noop_plan_still_requires_low_risk_tier_to_apply(app):
    Part(part_number="PLAN-NOOP", revision="A", description="Same").save()
    data = _pack(
        [{"partnumber": "PLAN-NOOP", "revision": "A", "description": "Same"}]
    )

    preview = _run(data)
    assert preview["required_permissions"] == ["imports.execute_low_risk"]
    assert all(
        entry["properties"] == [] or
        all(item["action"] not in {"add", "replace", "change", "clear"}
            for item in entry["properties"])
        for entry in preview["plan"]["parts"]
    )

    with pytest.raises(ImportPermissionError):
        _run(data, dry_run=False, permissions=set())
    with pytest.raises(ImportPermissionError):
        _run(data, dry_run=False, permissions=RESOURCE_WRITES)

    applied = _run(data, dry_run=False, permissions=LOW)
    assert applied["metrics"]["parts_created"] == 0
    assert applied["metrics"]["parts_updated"] == 0
