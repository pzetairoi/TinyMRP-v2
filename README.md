# TinyMRP v2

Lean, MongoDB-backed MRP starter focused on Bills of Materials (BOM), parts browser, and document packs (PDF binders, Excel BOM, visual lists).

Original project: pzetairoi/TinyMRP. This v2 rebuilds the stack (Flask + MongoDB + React/Vite), drops the legacy SQLite/Excel config, and adds modern auth and file handling.

---

## Features

- Auth and Roles: Flask-Security-Too, Argon2 hashing, role/permission editor.
- Parts & BOM APIs: MongoEngine models, server-side filters, where-used.
- Files & Thumbnails: file discovery, preview/drawing PNGs, 3MF viewer assets.
- Part numbering: server-side numbering schemes, revision policies, and history.
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

Create a local `.env` (do not commit it) or select one via `ENV_FILE` with at least:

- `SECRET_KEY`: Flask secret.
- `SECURITY_PASSWORD_SALT`: salt for Flask-Security.
- `MONGO_URI`: e.g. `mongodb://localhost:27017/tinymrp-v2`.
- File roots (canonical keys, see `app/__init__.py`):
  - `FILES_LOCAL_ROOT`: absolute path where deliverables are stored (host/container).
  - `FILES_URL_PREFIX`: URL prefix used by the app to serve files (e.g. `/deliverables` or `http://localhost:5001/Deliverables`).
  - Optional `FILES_UPSTREAM_BASE`: upstream file server base URL if proxying.
- Optional:
  - `FILE_HASH_MAX_BYTES`: compute/verify file hashes up to this size (0 to disable).
  - `VITE_BACKEND_URL`: dev proxy target for Vite (`frontend/vite.config.ts`).
  - `FORCE_HTTPS=true`: enforce HTTPS and set secure cookies.
  - `SECURITY_HEADERS_ENABLED=true`: send CSP + security headers.
  - `EXCEL_COMPILE_MAX_BYTES=10485760`: max upload size for Excel Compile.

Examples: `.env.dev.example`, `.env.docker.example`, `.env.server.example`.

---

## SolidWorks Add-in

Add-in project lives in `solidworks-addin/`.

### Requirements

- SolidWorks installed (API redistributables in `$(ProgramFiles)\SOLIDWORKS Corp\SOLIDWORKS\api\redist`)
- .NET Framework 4.8
- Inno Setup (only if you want to build the installer)

### Build

```powershell
dotnet msbuild solidworks-addin\TinyMRP.SolidWorksAddin.sln /p:Configuration=Release /p:Platform=x64
```

Output DLL:

`solidworks-addin/TinyMRP.SolidWorksAddin/bin/x64/Release/net48/TinyMRP.SolidWorksAddin.dll`

### Register / Unregister (manual)

```powershell
# Register
& "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe" "C:\Path\To\TinyMRP.SolidWorksAddin.dll" /codebase /tlb

# Unregister
& "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe" "C:\Path\To\TinyMRP.SolidWorksAddin.dll" /unregister
```

### Installer

The Inno Setup script is in `solidworks-addin/installer.iss`. It copies the build output and runs RegAsm.
Silent install example:

```powershell
TinyMRP_SolidWorksAddin_*.exe /VERYSILENT /SUPPRESSMSGBOXES /BACKENDURL="http://localhost:5000" /AUTHTOKEN="tmrp_xxx"
```

### Add-in Quick Start + Tokens

- Web dashboard:
  - `/ui/admin/addin` for Quick Start + Advanced defaults.
  - `/ui/addin/tokens` to create/revoke API tokens (shown once).
  - `/ui/admin/addin` for admins (token revoke + scheme preset flags).
- Add-in Configuration tab has **Quick Start** (presets + minimal inputs) and **Advanced** (full defaults).
- The add-in authenticates with a Bearer token stored in `AuthToken`.

### Configuration

- Primary config file: `%PROGRAMDATA%\TinyMRP\TinyMRP_config.txt`.
- Read order: ProgramData → install folder → `%LOCALAPPDATA%\TinyMRP\TinyMRP_config.txt`.
- If ProgramData is not writable, the add-in falls back to LocalAppData.
- Relative paths in the config are resolved from the add-in directory.
- Templates live under `solidworks-addin/TinyMRP.SolidWorksAddin/Templates/`.
- Numbering settings live in `BackendUrl`, `AuthToken`, `NumberingSchemeId`, `NumberingContextDefaults`.
- Property map and apply mode live in `PartNumberProperty`, `RevisionProperty`, `DisplayCodeProperty`, `NumberingApplyMode`.

### UI and Outputs

- Task pane tabs: Publish/BOM, Tools, Numbering, Configuration.
- Publish exports deliverables under `DeliverablesFolder`.
- BOM exports `*_FLATBOM.txt` and `*_TREEBOM.txt`, then zips them into `BOM_Folder\bom`.
- Child documents opened during export are closed automatically; only the root stays open.
- Numbering tab previews and allocates `PartNumber` + `Revision` via `/api/numbering/*`, then writes custom properties.

### Icons

The add-in and task pane icons are generated from `solidworks-addin/TinyMRP.SolidWorksAddin/Assets/logo.png`.

---

## Part Numbering API

Numbering schemes are managed server-side and consumed by the SolidWorks add-in.

### Scheme format

Schemes are built from ordered segments (no regex input):

- `literal`: `{ "kind": "literal", "value": "ASM" }`
- `field`: `{ "kind": "field", "field": "type|family|subfamily|project|site", "casing": "upper|lower|none", "pad_left": 2, "pad_char": "0" }`
- `seq`: `{ "kind": "seq", "padding": 6, "base": 10 }`
- `date`: `{ "kind": "date", "fmt": "YYYY|YY|MM|YYYYMM" }`

Global settings:

- `separator` (default `-`)
- `scope_mode`: `global|by_type|by_project|by_family|custom_keys`
- `scope_keys`: list used with `custom_keys`
- `seq`: `{ padding, base, start_at, reset_policy }`
- `revision`: `{ policy: alpha|numeric|none, start }`
- `validation_rules`: `{ max_length, allowed_charset, require_seq_segment }`

### Endpoints

- `GET /api/auth/check` (Bearer token)
- `GET /api/me/tokens`, `POST /api/me/tokens`, `DELETE /api/me/tokens/<id>`
- `GET /api/me/settings`, `PUT /api/me/settings`
- `GET /api/numbering/schemes`
- `POST /api/numbering/schemes`
- `GET /api/numbering/schemes/<id>`
- `PUT /api/numbering/schemes/<id>`
- `DELETE /api/numbering/schemes/<id>` (soft disable)
- `POST /api/numbering/schemes/validate`
- `POST /api/numbering/preview`
- `POST /api/numbering/allocate`
- `POST /api/numbering/parts/<part_number>/revise`

### Auth / permissions

- Scheme create/update requires admin/manager or `numbering.manage`.
- Preview and allocate are available to authenticated users.

### SolidWorks add-in usage

- The add-in loads schemes from `BackendUrl` (or `weblink`) and saves the selected scheme id in `TinyMRP_config.txt`.
- Allocation writes custom properties: `PartNumber`, `Revision`, `DisplayCode`, and `TinyMRP_SchemeId`.
- Property names can be customized via `PartNumberProperty`, `RevisionProperty`, `DisplayCodeProperty`.
- Parts remain unique on `(part_number, revision)` to preserve existing data flows; `display_code` provides `PN-REV`.

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

## Tests & Smoke Checks

Backend tests:

```powershell
python -m pytest -q
```

Frontend build:

```powershell
cd frontend
npm install
npm run build
```

API smoke test (requires a valid Bearer token):

```powershell
$env:BACKEND_URL = "http://localhost:5000"
$env:TOKEN = "<your_api_token>"
python scripts/smoke_api.py
```

Installer logic check:

```powershell
powershell -ExecutionPolicy Bypass -File tools\verify_installer_config_logic.ps1
```

Add-in build:

```powershell
dotnet msbuild solidworks-addin\TinyMRP.SolidWorksAddin.sln /p:Configuration=Release /p:Platform=x64
```

Installer build (Inno Setup):

```powershell
iscc solidworks-addin\installer.iss
```

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

## Production Deployment (Ubuntu + Docker)

This repo includes a ready-to-run Docker Compose stack (`mongo`, `app`, `nginx`). Follow these steps on a fresh Ubuntu server.

1) Install Docker + Compose plugin

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release; echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

2) Get the repo onto the server

```bash
sudo mkdir -p /opt && cd /opt
sudo git clone <your-repo-url> tinymrp_v2
cd /opt/tinymrp_v2
```

3) Prepare the Deliverables folder (host path)

```bash
sudo mkdir -p /srv/tinymrp/deliverables
# For testing, ensure the container can write thumbnails here
sudo chmod 0777 /srv/tinymrp/deliverables
# (optional tighter) sudo chown -R 1000:1000 /srv/tinymrp/deliverables
```

4) Configure environment (.env)

Edit your local `.env` and set at minimum:

- `DELIVERABLES_DIR=/srv/tinymrp/deliverables` (Linux absolute path)
- `HTTP_PORT=80` (or another free port if 80 is taken)
- Optional first-run admin seed: `DEFAULT_ADMIN_EMAIL`, `DEFAULT_ADMIN_PASSWORD`.

5) Build and start

```bash
sudo docker compose up -d --build
docker compose ps
```

6) Test

- App: `http://YOUR_SERVER_IP/` (or `http://YOUR_SERVER_IP:<HTTP_PORT>`)
- Files: `http://YOUR_SERVER_IP/deliverables/`
- First login: `admin@admin.com / admin` (or your `DEFAULT_ADMIN_*`).

### Mappings & Paths (repo-specific)

- Port mapping:
  - `docker-compose.yml` -> `nginx.ports`: host `${HTTP_PORT}` -> container `80`.
  - Set `HTTP_PORT` in `.env`.
- Deliverables bind mount:
  - `.env` -> `DELIVERABLES_DIR=/srv/tinymrp/deliverables`.
  - `docker-compose.yml` mounts `${DELIVERABLES_DIR}` to `/data/deliverables` in both `app` and `nginx`.
- App file roots and URL prefix:
  - `docker-compose.yml` sets `FILES_LOCAL_ROOT=/data/deliverables` and `FILES_URL_PREFIX=/deliverables` for the app.
  - Backend reads these in `app/__init__.py` and also exposes legacy aliases `FILE_ROOT_LOCAL`/`FILE_ROOT_HTTP` for internal services.
- Nginx static paths:
  - `docker/nginx/nginx.conf` serves both `/deliverables/` and `/Deliverables/` via `alias /data/deliverables/`.
- Frontend file base:
  - `frontend/.env.production` uses `VITE_FILES_BASE_URL=/deliverables`; UI normalizes links accordingly.

### First-Run Seeding

On first boot, if the database has no users, the app auto-creates roles and a default admin using `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` (or falls back to `admin@admin.com` / `admin`).

### Troubleshooting Quick Checks

- Port busy - change `.env: HTTP_PORT` and `docker compose up -d`.
- App 502 - `docker compose logs -f app` and `docker compose logs -f nginx`.
- Files 404 - verify host folder path and mounts: `docker compose exec app sh -lc 'ls -la /data/deliverables'`.
- Thumbnails not writing - relax perms on `/srv/tinymrp/deliverables` during testing.

---

## Frontend (React/Vite)

- Build outputs to `app/static/parts-ui` (manifest included). The Flask routes under `/ui/*` read this manifest to inject JS/CSS.
- Dev server: `npm run dev` and set `VITE_BACKEND_URL=http://localhost:5000` to proxy API requests.

Main UI routes:

- `/ui/parts` - React shell for browsing parts.
- `/ui/part/<pn>?rev=<rev>` - part detail; links from PDF binder and Excel BOM.
- `/ui/bom/<pn>?rev=<rev>` - BOM view (when enabled in the current build).

---

## Document Packs API (PDF/Excel)

Endpoints:

- `GET /api/docpacks/options?pn=PN&rev=REV&depth=full|top` - available `file_types` and canonical `processes`.
- `POST /api/docpacks/build` - Generates a ZIP or a single PDF depending on options.

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
- Files config uses canonical keys `FILES_LOCAL_ROOT`, `FILES_URL_PREFIX`, `FILES_UPSTREAM_BASE`. Backward-compatible aliases `FILE_ROOT_LOCAL` and `FILE_ROOT_HTTP` remain for older code paths.
- Frontend build artifacts are written to `app/static/parts-ui` by `npm run build` from the `frontend` directory.

---

## License

This repository inherits the spirit of the original TinyMRP project. Add your license here if distributing.
