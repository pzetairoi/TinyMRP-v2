from app.models.part import Part
from app.services.canonical_fields import sync_part_canonical_fields
from app.services.processmeta import load_process_meta, normalize_processes


def test_custom_process_library_normalizes_aliases():
    meta = load_process_meta(
        overrides={
            "anodising": {
                "aliases": ["anodize", "anodizing"],
                "color": "118, 113, 113",
                "icon": "unknown.svg",
            },
            "others": {
                "color": "118, 113, 113",
                "icon": "unknown.svg",
            },
        }
    )

    assert normalize_processes({"process": "anodizing"}, meta) == ["anodising"]
    assert normalize_processes({"process": "not in library"}, meta) == ["others"]


def test_custom_process_can_reclassify_part_that_was_other():
    default_meta = load_process_meta()
    part = Part(part_number="P-100", revision="", attrs={"process": "anodising"})

    sync_part_canonical_fields(part, process_meta=default_meta)
    assert part.processes == ["others"]

    custom_meta = load_process_meta(
        overrides={
            "anodising": {
                "aliases": ["anodize", "anodizing"],
                "color": "118, 113, 113",
                "icon": "unknown.svg",
            },
            "others": {
                "color": "118, 113, 113",
                "icon": "unknown.svg",
            },
        }
    )

    sync_part_canonical_fields(part, process_meta=custom_meta)
    assert part.processes == ["anodising"]
    assert part.canonical["processes"] == ["anodising"]
