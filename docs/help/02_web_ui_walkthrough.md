# Web UI Walkthrough

This page explains how to use each major area of the TinyMRP web app.

## Main Navigation

Top navigation and user menu are permission-aware. If a menu is missing, your role does not currently include that permission.

Common entries:

- `Inventory` -> `/ui/parts`
- `Import` -> `/ui/upload-pack`
- `Jobs` -> `/admin/jobs/`
- `Orders` -> `/admin/orders/`
- `Suppliers` -> `/admin/suppliers/`
- `Customers` -> `/admin/customers/`
- User menu -> `Help`, `Tokens`, `Admin Dashboard`, `Audit Log`

## Inventory (`/ui/parts`)

### What it does

- Lists part revisions with search, sort, and filters.
- Opens Part Detail for any row.
- Supports pick mode for Jobs and Orders line selection.

### Important filters

- `Approved`
- `Full files`
- `Minimum properties`
- `Used in job` + `Job number contains`
- Column-level filters for PN, rev, description, process, material, finish.

### Pick mode (`/ui/parts?pick=1`)

- Used by Job BOM and Order line editors.
- Allows multi-select and quantity entry per selected part.
- Sends selected rows back to the opener window.

## Part Detail (`/ui/part/:pn?rev=...`)

Part Detail is the operational center for one part revision.

### Left panel

- Hero image and quick file buttons (PDF, DXF, datasheet, 3MF, PLY, STL if present).
- Approval and uploader metadata.
- Missing-property signal when critical fields are absent.

### Main tabs

- `Drawing`: opens drawing preview and PDF link when available.
- `All attributes`: full attribute dictionary for the part.
- `3D Preview`: choose among available 3D files and view in-browser.
- `Associated files`: download/delete existing extras and upload more (edit permission required).
- `Doc Packs`: build and download targeted output packages.
- `Other versions`: jump to other revisions of the same PN.
- `Jobs & Orders`: trace where this part is consumed in jobs and orders.
- `Notes & Comments`: team notes and comment thread.
- `Actions`: update file links and optionally delete part (permission-gated).

### Doc Packs tab (key controls)

- Depth: `Top Level only` or `Full BOM`.
- Consumed: `Hide consumed` or `Show consumed`.
- Classified filter: `Hide`, `Show`, `Only`.
- Process mode: `All` or `Only selected`.
- Output selection: selected files, Excel BOM, PDF binder, index, visual summary, hardware summary, cover page, where-used report.
- Binder options: cover/index/visual/where-used/datasheets/hardware/page numbers/flat patterns.
- Stamps: quote, confidential, approved, WIP, in progress.
- One-click `Fabrication Pack` preset for fabrication-oriented outputs.

### Actions tab behavior

- `Update files`: rescans storage for this PN/rev; optional recursive child scan.
- `Delete part`: optional child delete for children not used elsewhere.

## BOM View (`/ui/bom` and `/ui/bom/:pn`)

### What it does

- Lazy-loaded BOM tree with expand-on-demand.
- Where-used table below the tree.
- Tree nodes link to Part Detail.

### Typical use

1. Open `/ui/bom/:pn`.
2. Expand subassemblies.
3. Use where-used table to find upstream parents.

## Dashboard (`/ui/dashboard`)

### What it shows

- Total parts, recent updates, approved counts.
- Document coverage (PDF/PNG/DXF/STEP/datasheet).
- Data health (missing material/process/description).
- Top processes and top hardware usage.
- Recently updated parts.

## Import Upload Pack (`/ui/upload-pack`)

### What it does

- Uploads ZIP bundles containing BOM + deliverables + associated files.
- Supports `Dry run` and `Strict structure checks`.
- Shows progress, timings, diagnostics, warnings, and errors.
- Offers downloadable JSON import report for troubleshooting.

### Expected ZIP structure

```text
bom/
  *_FLATBOM.txt
  *_TREEBOM.txt
deliverables/
  <group>/...
extra/
  <PN>/<REV_OR__no_rev__>/...
```

## Tokens (`/ui/addin/tokens`)

- Create personal API tokens for the SolidWorks add-in.
- Token value is shown once at creation.
- Revoke tokens that are no longer needed.

## Add-in Admin (`/ui/admin/addin`)

Admin-only workspace for add-in governance:

- View users and revoke their tokens.
- Manage numbering scheme preset/recommended/visibility flags.
- Build and validate numbering schemes with advanced segment editor.

## Tools (`/tools`)

- Download latest SolidWorks add-in installer.
- Download SolidWorks custom property tab templates.
- Run Excel Compile workflow and download compiled ZIP output.
