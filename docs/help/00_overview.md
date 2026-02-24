# Overview

TinyMRP is a manufacturing data platform that combines:

- A web app for parts, BOMs, jobs, orders, suppliers, customers, and document packs.
- A SolidWorks add-in for publishing deliverables, creating upload packs, and allocating part numbers.

This help content is written for day-to-day users. It focuses on what to do, where to click, and what result to expect.

## Start Here By Role

### Design and engineering

- Use `Web UI walkthrough` for Inventory, Part Detail, BOM, and Doc Packs.
- Use `SolidWorks add-in walkthrough` for Publish/BOM, Tools, Numbering, and Configuration tabs.

### Purchasing and planning

- Use `End-to-end workflow` for progressive ordering across multi-level BOMs.
- Focus on Jobs: `Parts in Orders`, `Over-Ordered Parts`, and `Parts Not Yet Ordered` (Flat/Tree toggle).

### Admin and IT

- Use `Server installation` for deployment, environment variables, and upgrades.
- For Windows workstation hardening and LAN-only exposure, use `deploy/windows/README.md`.
- Use `Customization and admin settings` for users, roles, scoping, branding, and limits.

## Core Concepts

- Part revision: TinyMRP tracks files by `(Part Number, Revision)`.
- Deliverables: model and drawing outputs like PDF, DXF, STEP, 3MF, PLY, STL, PNG.
- Associated files: extra files linked to a part revision (photos, scans, reports).
- Upload Pack: ZIP with `bom/`, `deliverables/`, and optional `extra/`.
- Doc Pack: generated package (binder/index/visual/hardware/Excel/etc).

## How To Use This Help Quickly

- Use the right-side `On this page` panel in `/help` to jump by heading.
- Use the heading search box for exact terms such as `Over-Ordered`, `Upload Pack`, `Numbering`, `Scope of supply`.
- For API and route lookup, use `Reference (auto-updated)`.

## Help Sections

- `01_server_installation.md`: deployment and runtime operations.
- `02_web_ui_walkthrough.md`: complete web app usage.
- `03_addin_installation.md`: installer, registration, first connection.
- `04_addin_ui_walkthrough.md`: detailed add-in tab behavior.
- `05_end_to_end_workflow.md`: practical release and purchasing flows.
- `06_customization_admin.md`: admin operations and settings.
- `07_troubleshooting.md`: issue-driven diagnostics.
- `08_reference_auto.md`: generated routes, APIs, env vars, and add-in options.

## Keeping Help Current

Help pages are generated from `docs/help/`:

1. Edit markdown files in `docs/help/`.
2. Run `flask --app run.py help build`.
3. Commit updated files in `app/static/help/`.
