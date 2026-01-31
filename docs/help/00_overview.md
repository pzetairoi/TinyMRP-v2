# Overview

TinyMRP is a parts and documentation hub for manufacturing teams. It keeps parts, revisions, deliverables, and doc packs in one place so you can find and share the right data quickly.

This Help page is written for non-IT users. It explains what to click, what you should see, and what to do next.

## How this help is generated / how to update it

This Help page is built from markdown files in `docs/help/` plus a small amount of auto-generated reference data.

To update the help:

1) Edit the markdown files in `docs/help/`.
2) Run `flask help build` from the server project.
3) Commit the generated files in `app/static/help/` so the help page is up to date.

The reference section is auto-filled from the codebase using placeholders like `{{AUTO_UI_PAGES}}` and `{{AUTO_API_ENDPOINTS}}`. These are replaced when you run the build command.

**Tip:** Keep headings consistent and avoid deep nesting so the table of contents stays clean.

## What you can do in TinyMRP

- Search and browse parts and revisions.
- View deliverables (PDF, DXF, STEP, 3MF, PLY, STL, and more).
- Generate doc packs (binder, index, visuals, BOM spreadsheets).
- Share data with suppliers, customers, and internal teams.
- Manage users, roles, permissions, and branding.

## Who this guide is for

- Engineers and designers who publish deliverables.
- Production and purchasing teams who consume BOMs and drawings.
- Administrators who manage users, roles, and system settings.

## Quick navigation

- Server and web app: installation, usage, and customization.
- SolidWorks add-in: installation, usage, and options.
- End-to-end workflow: create parts to doc packs.
- Reference: routes, UI pages, API endpoints, and options.
