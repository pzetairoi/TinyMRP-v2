# UX Lift-Up Overview

This document summarizes the new Dashboard, Part Insights, and Notes/Comments features, plus Parts list UX improvements.

## Dashboard

Endpoint: `GET /api/dashboard/summary`

Contents:
- KPI cards: total parts, updated last 7 days, PDF coverage percent, release signals (approved/initialed).
- Data health: counts of missing material, process, description.
- Doc coverage breakdown: PDF/PNG/DXF/STEP/Datasheet counts per part revision.
- Top processes list.
- Recently updated parts table (PN, rev, description, updated_at).
- Top hardware used table (where-used count and total qty).

Performance:
- Aggregation pipelines are used for doc coverage and top processes.
- A 45-second in-memory TTL cache is used with a lock (per user).

## Part Insights

Endpoint: `GET /api/parts/<pn>/insights?rev=...`

Rules:
- Classification (deterministic):
  - `hardware` if processes or category indicate hardware/fasteners.
  - `purchase` if purchase processes or category indicate purchased parts.
  - `assembly` if assembly processes or category indicate assembly.
  - `sheet_metal` if sheet-metal processes, category, or material.
  - `fabrication` fallback.
- Normalized processes: uses `processmeta` aliases.
- Missing fields: material, process, description.
- Deliverables present: pdf/png/dxf/step/datasheet.
- Recommendations:
  - hardware/purchase: datasheet or link.
  - sheet_metal: pdf and dxf.
  - assembly: pdf and BOM presence.
- Where-used stats: count of parents and total qty from BOMLink.

## Notes and Comments

Storage:
- `Part.attrs.notes` (string)
- `Part.attrs.comments` (array of `{ts, author, text}`)

Endpoints:
- `POST /api/parts/<pn>/notes`
- `POST /api/parts/<pn>/comments`

Permissions:
- Read: any viewer with items access.
- Write: `items.edit` (admin or editor).
- Audit logs are created on save.

## Parts List UX

Updates:
- Coverage icons for PDF/DXF/STEP/Datasheet per row.
- Quick filters: Missing PDF, Missing Material, Hardware, Sheet metal.
- `parts_lazy` returns `has_pdf`, `has_dxf`, `has_step`, `has_datasheet`, `has_png` flags.

## Indexes Added

On `parts` collection:
- `updated_at`
- `processes`
- `description`
- `attrs.material`
- `attrs.finish`
