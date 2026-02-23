# SolidWorks Add-in Walkthrough

This guide maps each add-in tab to practical tasks.

## Publish/BOM Tab

### Deliverables

Model outputs:

- PNG
- STEP
- eDrawings
- 3MF
- PLY
- STL

Drawing outputs:

- PNG drawing
- PDF
- DXF
- eDrawings drawing

### Publish options

- `Overwrite files`: replace existing outputs.
- `Top level only`: limit assembly processing to root item.

### Associated files

- `Manage associated files...` opens the extra-files manager.
- Data is stored in custom property `TINYMPR_ASSOC_FILES`.

### Upload pack actions

- `Create upload pack` builds ZIP from selected deliverables and associated files.
- Include toggles:
  - `Include deliverables`
  - `Include associated files`

### BOM actions

- `Process BOM` exports BOM text files for import.

### Progress and run controls

- Progress bars for `Create files` and `Process BOM`.
- `Cancel current task` aborts long operations.
- `Open last run log` opens detailed run log.

## Tools Tab

### Model utilities

- `Freeze model`
- `Unfreeze model`
- `Normalize units`

### Visibility utilities

Hide selected reference geometry and sketch categories in bulk:

- Origin, planes, axes, points, coordinate systems
- 2D/3D sketches, spline/curve helpers
- Envelope and related helper geometry

Controls include `Select all`, `Clear`, `Hide selected features`, and cancellation support.

## Numbering Tab

### Quick actions

- `Preview Partnumber`
- `Allocate & Apply`
- `Allocate and rename`

### Context and presets

- Preset scheme dropdown with refresh.
- Context fields such as type, family, subfamily, project, site.
- Live preview fields for part number, revision, and display code.

### Advanced numbering editor

- Full scheme builder: segments, separator, scope mode, scope keys.
- Sequence controls: padding, base, start, reset policy.
- Revision controls: policy and start value.
- Validation rules: max length, allowed charset, require sequence segment.
- Segment operations: add, update, remove, move up/down.
- `Validate scheme`, `Save scheme`, `Deactivate`.

### Advanced allocation and rename

- Allocation scope: active config, all configs, or selected configurations.
- Optional document-level property write.
- Rename dry run support before commit.
- Rename behavior options include safe mode and reference-aware mode.

## Configuration Tab

Configuration has two sub-tabs: `Quick Start` and `Advanced`.

### Quick Start

- Backend URL
- Auth token
- Preset scheme selection
- Numbering defaults (property names, apply mode, context defaults)
- Deliverables folder
- `Save settings`

### Advanced

- Template paths:
  - Blank sheet template
  - BOM template
- Drawing export settings:
  - DXF sheet names
- Server links:
  - Web link
  - Backend URL
  - Auth token
- Diagnostics and actions:
  - `Test connection`
  - `Apply server defaults`
  - `Preview next`
  - `Go to Numbering`
  - `Diagnostics`
- Save actions:
  - `Save local config`
  - `Save server settings`

## Recommended Daily Flows

### Release package from CAD

1. Open model/assembly.
2. In `Publish/BOM`, select required outputs.
3. Run `Create files`.
4. Optionally run `Create upload pack`.
5. Import ZIP in web app (`/ui/upload-pack`).

### Controlled numbering + rename

1. In `Numbering`, select preset and context.
2. Preview.
3. Allocate and apply.
4. Run rename dry run.
5. Execute rename only after preview looks correct.
