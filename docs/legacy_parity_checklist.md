# Legacy Parity Checklist

This checklist captures legacy behaviors from `OLD/SourceCode` and maps them to current TinyMRP-v2 implementations, with verification notes.

## PDF Binder / Visual Index

- Hardware Summary in binder
  - Legacy: `OLD/SourceCode/app/tinylib/publisher.py` `visual_list()` builds `hardlist` and adds a "Hardware Summary" table page.
  - Current: `app/services/docpacks.py` `_hardware_summary_rows` + `_hardware_summary_pdf`, option `binder_add_hardware_summary` in `DocPackOptions`; wired through `app/views/docpacks.py` + UI checkbox in `frontend/src/pages/PartDetailPage.tsx`.
  - Verification: `tests/test_docpacks_binder.py` asserts "Hardware Summary" appears in binder text when option enabled.

- Visual index boxes / borders
  - Legacy: `OLD/SourceCode/app/tinylib/publisher.py` `BoxyGrid.draw()` draws thick colored rectangles and borders.
  - Current: `app/services/docpacks.py` `_visual_list_pdf` increases stroke darkness/width for card borders.
  - Verification: `tests/test_docpacks_binder.py` checks stroke width >= 1.0 and rectangle ops.

- Page numbers bottom-right
  - Legacy: `OLD/SourceCode/app/tinylib/publisher.py` `pdf_pagenum()` draws bottom-right page number box/text.
  - Current: `app/services/docpacks.py` `_overlay_numbers_and_stamps` draws `{i} / {total}` and honors `binder_page_numbers`.
  - Verification: `tests/test_docpacks_binder.py` checks each non-cover page for the expected page number text.

- Centered approval / WIP / in-progress stamp
  - Legacy: `OLD/SourceCode/app/tinylib/publisher.py` `pdf_pagenum()` draws stamp centered with page size.
  - Current: `app/services/docpacks.py` `_overlay_numbers_and_stamps` uses `translate(W/2, H/2)` for stamps; `inprogress` uses centered text; status mapping is approved > wip > inprogress.
  - Verification: `tests/test_docpacks_binder.py` checks center translate; manual spot-check for approved vs in-progress stamp assets.

- Cover/header page with timestamp
  - Legacy: `OLD/SourceCode/app/tinylib/publisher.py` binder cover uses title/subtitle + timestamp.
  - Current: `app/services/docpacks.py` `_cover_page_pdf` includes `Generated:` timestamp, PN/REV, and description.
  - Verification: `tests/test_docpacks_binder.py` asserts cover page text contains `Generated:` and the root PN.

- Cover page layout + TinyMRP logo
  - Legacy: cover page kept a slim header and logo in top corner (see `OLD/SourceCode/app/static/images` + binder cover flowables).
  - Current: `app/services/docpacks.py` `_cover_page_pdf` now only shows PN/REV + description at top, author/process/generated/related file at bottom, and draws logo top-right; cover is optional via `binder_add_cover` / `want_cover_page`.
  - Verification: Manual (cover page content + logo placement in binder and standalone cover export).

- Index entries include part number + description
  - Legacy: index entries used `partnumber + revision + description` in binder bookmarks.
  - Current: `app/services/docpacks.py` binder index entries use PN + description labels.
  - Verification: Manual (index page text).

- Visual index inclusion is optional + standalone export
  - Legacy: visual index always appended to binder.
  - Current: `app/services/docpacks.py` uses `binder_add_visual_list` for binder inclusion and `want_visual_list` for standalone; UI in `frontend/src/pages/PartDetailPage.tsx`.
  - Verification: Manual (binder vs standalone output toggles).

- Where-used report (printable)
  - Legacy: not available as a printable report (only on-screen list).
  - Current: `app/services/docpacks.py` `_whereused_report_pdf` with `binder_add_whereused` / `want_whereused_report` options.
  - Verification: Manual (where-used report in binder + standalone PDF).

## Excel BOM

- Replace "Approved By" column with "Total Qty"
  - Legacy: `OLD/SourceCode/app/tinylib/publisher.py` `dictlist_to_excel()` uses total quantities.
  - Current: `app/services/docpacks.py` `_excel_bom_bytes` uses `total qty` header at the legacy position and sources values from `full_qty_map`.
  - Verification: `tests/test_excel_bom_total_qty.py` confirms header uses `total qty` and omits approved columns.

## Filenames / Output Naming

- Timestamp suffix + Windows-safe length
  - Legacy: output names include timestamps via `datetime.now().strftime(...)`.
  - Current: `app/services/filenames.py` `build_output_name()` applies safe chars + date suffix; used in `app/services/docpacks.py` and `app/views/tools.py`.
  - Verification: `tests/test_filenames.py` enforces max length, date suffix, and Windows-safe characters.

- Output name requirement
  - Legacy: compile/docpack flows prompted for an output name.
  - Current: `app/views/docpacks.py` validates `output_name`/`filename` when provided; `frontend/src/pages/PartDetailPage.tsx` adds an optional output name input; defaults use `build_output_name()`.
  - Verification: Manual (API returns 400 for blank output name).

## Approval State + Description Order

- Correct approval stamp mapping
  - Legacy: `pdf_pagenum()` selects `approved` vs `wip` based on status.
  - Current: `app/services/docpacks.py` selects `approved` > `wip` > `inprogress` and maps in-progress to a dedicated centered stamp.
  - Verification: Manual (stamp selection in docpack UI).

- Description field precedence
  - Legacy: `dictlist[i]["description"]` derived from part description.
  - Current: `app/services/docpacks.py` `_part_description` prioritizes `Part.description`; `app/views/parts.py` preserves the same precedence for API responses.
  - Verification: Manual (visual list + cover page text).

## Part Detail UI

- Process icons for all processes
  - Legacy: `OLD/SourceCode/app/tinylib/models.py` `get_process_icons()` included all processes (process/process2/process3).
  - Current: `app/services/processmeta.py` + `app/services/insights.py` normalize + merge attrs and `Part.processes`; `frontend/src/pages/PartDetailPage.tsx` renders icons per process.
  - Verification: Manual (assembly with multiple processes shows multiple chips).

## Fabrication Pack

- Fabrication pack covers all fabrication processes + scope-of-supply
  - Legacy: `OLD/SourceCode/app/tinylib/views.py` `/fabrication` builds welding-based pack with scope-of-supply Excel and all docs (PDF/DXF/STEP/PNG).
  - Current: `app/services/docpacks.py` `fabrication_pack` forces a fabrication process set, excludes consumed parts for scope-of-supply, and includes required docs via selected files + Excel BOM.
  - Verification: Manual (fabrication pack output contents + Excel BOM).

## Job BOM Editor

- Remove line works (or hidden when no permission)
  - Legacy: `OLD/SourceCode/app/tinylib/views.py` job BOM manipulation via add/remove routes.
  - Current: `app/views/admin_jobs.py` returns `line_rev` and uses it for update/remove; `app/static/js/job_bom_editor.js` uses `line_rev` and hides actions when `can_manage` is false.
  - Verification: `tests/test_job_bom_remove.py` validates removal with stored line rev.
