from pathlib import Path


PARTS_PAGE = Path(__file__).resolve().parents[1] / "frontend" / "src" / "pages" / "PartsPage.tsx"


def test_normal_parts_header_uses_only_search_and_column_selection():
    source = PARTS_PAGE.read_text(encoding="utf-8")

    assert 'placeholder="Search part number or description"' in source
    assert 'buttonLabel="Columns"' in source
    assert "flex-grow-1" in source
    for obsolete_filter in (
        "approved_only",
        "full_files",
        "min_props",
        "used_in_job",
        "job_number",
    ):
        assert obsolete_filter not in source


def test_job_only_picker_control_is_preserved():
    source = PARTS_PAGE.read_text(encoding="utf-8")

    assert 'id="jobOnly"' in source
    assert "Job parts only" in source
    assert "payload.job_only = true" in source
