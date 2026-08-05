from pathlib import Path


_FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "src"
PARTS_PAGE = _FRONTEND / "pages" / "PartsPage.tsx"
# Column-filter defaults and legacy-meta normalisation were extracted from the
# page into their own module, so the typed-filter contract now spans both files.
COLUMN_FILTERS = _FRONTEND / "lib" / "columnFilters.ts"


def _parts_filter_source() -> str:
    return PARTS_PAGE.read_text(encoding="utf-8") + COLUMN_FILTERS.read_text(encoding="utf-8")


def test_normal_parts_header_uses_only_search_and_column_selection():
    source = PARTS_PAGE.read_text(encoding="utf-8")

    assert 'placeholder="Search part number, description, notes or comments"' in source
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


def test_parts_columns_expose_typed_row_filters():
    source = _parts_filter_source()

    assert 'filterDisplay="row"' in source
    assert "showFilterMenu={false}" in source
    # Filter inputs morph with the field data type.
    assert "field.data_type === 'boolean'" in source
    assert "field.data_type === 'number'" in source
    assert "field.data_type === 'date'" in source
    assert 'type="number"' in source
    assert 'type="date"' in source
    assert "FilterMatchMode.DATE_IS" in source
    # Filters keep the flat {value, matchMode} shape of the parts_lazy contract.
    assert "part_number: { value: '', matchMode: FilterMatchMode.CONTAINS }" in source
    # Leftover menu-style metas are unwrapped instead of being sent as constraints.
    assert "Array.isArray(current.constraints)" in source
