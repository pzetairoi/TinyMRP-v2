# TinyMRP v2

Lean, MongoDB‑backed MRP starter focused on Bills of Materials (BOM), parts browser, and document packs (PDF binders, Excel BOM, visual lists).

Original project: pzetairoi/TinyMRP. This v2 rebuilds the stack (Flask + MongoDB + React/Vite), drops the legacy SQLite/Excel config, and adds modern auth and file handling.

---

## Features

- Auth and Roles: Flask‑Security‑Too, Argon2 hashing, role/permission editor.
- Parts & BOM APIs: MongoEngine models, server‑side filters, where‑used.
- Files & Thumbnails: file discovery, preview/drawing PNGs, 3MF viewer assets.
- Document Packs:
  - PDF binder with cover page, index (with dot leaders), and Visual Summary listed first.
  - Automatic page numbers; optional watermarks (quote, classified, approved, WIP).
  - Include/exclude datasheets; configurable stamps.
  - Excel BOM (openpyxl) with thumbnails, hyperlinks, and attribute columns.
- React UI (Vite build) for part detail and visual list pages.

---

## Tech Stack

- Backend: Python 3.12, Flask 3.x, MongoEngine 0.29.x, PyMongo 4.x.
- DB: MongoDB 6/7 (local or Atlas).
- Frontend: React 19, Vite 7, PrimeReact, ThreeJS (3MF viewer).
- Dev: `python-dotenv`, Docker Compose, optional Nginx for static deliverables.

---

## Configuration

Create a `.env` (or select one via `ENV_FILE`) with at least:

- `SECRET_KEY`: Flask secret.
- `SECURITY_PASSWORD_SALT`: salt for Flask‑Security.
- `MONGO_URI`: e.g. `mongodb://localhost:27017/tinymrp-v2`.
- File roots (canonical keys, see `app/__init__.py`):
  - `FILES_LOCAL_ROOT`: absolute path where deliverables are stored (host/container).
  - `FILES_URL_PREFIX`: URL prefix used by the app to serve files (e.g. `/deliverables` or `http://localhost:5001/Deliverables`).
  - Optional `FILES_UPSTREAM_BASE`: upstream file server base URL if proxying.
- Optional:
  - `FILE_HASH_MAX_BYTES`: compute/verify file hashes up to this size (0 to disable).
  - `VITE_BACKEND_URL`: dev proxy target for Vite (`frontend/vite.config.ts`).

Examples: `.env.dev.example`, `.env.docker.example`, `.env.server.example`.

---

## Quick Start (local dev)

PowerShell snippet (from `handycommands.txt`):

```powershell
# 1) Serve deliverables through a tiny nginx
$env:FILES_LOCAL_ROOT = "C:/CADEXPORT"
docker run --rm -d --name tinymrp-nginx-static -p 5001:80 `
  -v "${PWD}/docker/nginx/nginx.static.conf:/etc/nginx/nginx.conf:ro" `
  -v "${env:FILES_LOCAL_ROOT}:/data/deliverables:ro" nginx:1.27-alpine

# 2) Run the app with the dev env file
$env:ENV_FILE = '.env.dev.example'
python run.py

# 3) Seed roles and create an admin
flask --app run.py user seed-roles
flask --app run.py user create --email admin@admin.com --password admin
flask --app run.py user grant-admin --email admin@admin.com

# 4) Build the frontend (writes to app/static/parts-ui)
cd frontend
npm install
npm run build
```

Visit http://localhost:5000 (app) and http://localhost:5001/Deliverables (files).

---

## Docker Compose

```bash
docker compose up --build
```

Useful snippets (from `handycommands.txt`):

```bash
docker compose up -d
docker compose exec app flask --app run.py user seed-roles
docker compose exec app flask --app run.py user create --email admin@admin.com --password admin
docker compose exec app flask --app run.py user grant-admin --email admin@admin.com

# Recreate just the app container
docker compose up -d --force-recreate app
```

---

## Frontend (React/Vite)

- Build outputs to `app/static/parts-ui` (manifest included). The Flask routes under `/ui/*` read this manifest to inject JS/CSS.
- Dev server: `npm run dev` and set `VITE_BACKEND_URL=http://localhost:5000` to proxy API requests.

Main UI routes:

- `/ui/parts` — React shell for browsing parts.
- `/ui/part/<pn>?rev=<rev>` — part detail; links from PDF binder and Excel BOM.
- `/ui/bom/<pn>?rev=<rev>` — BOM view (when enabled in the current build).

---

## Document Packs API (PDF/Excel)

Endpoints:

- `GET /api/docpacks/options?pn=PN&rev=REV&depth=full|top` → available `file_types` and canonical `processes`.
- `POST /api/docpacks/build` → Generates a ZIP or a single PDF depending on options.

Example payload:

```json
{
  "pn": "ASM-1001", "rev": "A",
  "depth": "full",
  "include_consumed": false,
  "classified": "show",
  "processes": ["welding", "machine"],
  "process_mode": "all",
  "file_types": ["pdf", "datasheet"],
  "excel_bom": true,
  "selected_files": true,
  "pdf_binder": true,
  "visual_list": true,
  "binder_add_index": true,
  "binder_add_datasheets": false,
  "binder_page_numbers": true,
  "stamp_quote": false, "stamp_confidential": false, "stamp_approved": false,
  "stamp_wip": false, "stamp_inprogress": false
}
```

Behavior highlights:

- Visual Summary is listed first in the index, then the root (father) and children.
- Cover page is page 1 (page numbers overlaid skip the cover when enabled).
- Excel BOM includes thumbnails, hyperlinks to the app, and normalized attributes.

---

## CLI Utilities

User management:

- `flask --app run.py user seed-roles`
- `flask --app run.py user create --email <email> --password <pw>`
- `flask --app run.py user grant-admin --email <email>`

Data helpers (see `app/cli.py`):

- Demo data: `flask --app run.py user seed-parts`, `flask --app run.py user seed-bom`.
- Importer: `flask --app run.py importcmd zip --file <path>.zip`.
- File discovery: `flask --app run.py files scan-one --pn PN --rev REV`.

---

## Notes & Tips

- CSRF is enabled; some API blueprints are explicitly exempted where required for SPA calls.
- Files config uses canonical keys `FILES_LOCAL_ROOT`, `FILES_URL_PREFIX`, `FILES_UPSTREAM_BASE`. Backward‑compatible aliases `FILE_ROOT_LOCAL` and `FILE_ROOT_HTTP` remain for older code paths.
- Frontend build artifacts are written to `app/static/parts-ui` by `npm run build` from the `frontend` directory.

---

## License

This repository inherits the spirit of the original TinyMRP project. Add your license here if distributing.

