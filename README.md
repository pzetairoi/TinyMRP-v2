# TinyMRP v2

Lean, MongoDB-backed MRP starter focused on Bills of Materials (BOM), parts browser, and document packs (PDF binders, Excel BOM, visual lists).

Original project: pzetairoi/TinyMRP. This v2 rebuilds the stack (Flask + MongoDB + React/Vite), drops the legacy SQLite/Excel config, and adds modern auth and file handling.

---

## Features

- Auth and Roles: Flask-Security-Too, Argon2 hashing, role/permission editor.
- Parts & BOM APIs: MongoEngine models, server-side filters, where-used.
- Files & Thumbnails: file discovery, preview/drawing PNGs, 3MF viewer assets.
- Upload Pack: ZIP import with BOM + deliverables + associated files.
- Part numbering: server-side numbering schemes, revision policies, and history.
- Document Packs:
  - PDF binder with cover page, index (with dot leaders), and Visual Summary listed first.
  - Automatic page numbers; optional watermarks (quote, classified, approved, WIP).
  - Include/exclude datasheets; configurable stamps.
  - Excel BOM (openpyxl) with thumbnails, hyperlinks, and attribute columns.
- React UI (Vite build) for part detail and visual list pages.
- Business modules: Jobs, Suppliers, Customers, Orders (admin UI + REST APIs).

---

## Tech Stack

- Backend: Python 3.12, Flask 3.x, MongoEngine 0.29.x, PyMongo 4.x.
- DB: MongoDB 6/7 (local or Atlas).
- Frontend: React 19, Vite 7, PrimeReact, ThreeJS (3MF viewer).
- Dev: `python-dotenv`, Docker Compose, optional Nginx for secure file offload.

---

## Configuration

Create a local `.env` (do not commit it) or select one via `ENV_FILE` with at least:

- `SECRET_KEY`: Flask secret.
- `SECURITY_PASSWORD_SALT`: salt for Flask-Security.
- `MONGO_URI`: e.g. `mongodb://localhost:27017/tinymrp-v2`.
- File roots (canonical keys, see `app/__init__.py`):
  - `FILES_LOCAL_ROOT`: absolute path where deliverables are stored (host/container).
  - `FILES_URL_PREFIX`: URL prefix for protected files when Nginx is fronting the app (e.g. `/deliverables`).
  - Optional `FILES_UPSTREAM_BASE`: upstream file server base URL if proxying.
  - `FILES_PUBLIC_URLS=false`: allow direct public file URLs (off by default).
  - `FILES_ACCEL_REDIRECT_PREFIX=/__files`: internal Nginx location used for X-Accel-Redirect.
  - `FILES_ALLOW_LEGACY_TOKENS=false`: allow legacy base64 file tokens (off by default).
- Optional:
  - `TINYMRP_SECURITY_MODE=compat|strict`: security profile (default compat).
  - `TINYMRP_ALLOWED_ORIGINS`: comma-separated CORS allowlist (strict mode requires this).
  - `TINYMRP_CORS_CREDENTIALS=true`: allow credentials when using an explicit allowlist.
  - `TINYMRP_MAX_CONTENT_MB`: global request size cap (falls back to Upload Pack max).
  - `TINYMRP_RUNTIME_SECRETS_PATH`: override runtime secrets file path (compat mode only).
  - `FILE_HASH_MAX_BYTES`: compute/verify file hashes up to this size (0 to disable).
  - `VITE_BACKEND_URL`: dev proxy target for Vite (`frontend/vite.config.ts`).
  - `FORCE_HTTPS=true`: enforce HTTPS and set secure cookies.
  - `SECURITY_HEADERS_ENABLED=true`: send CSP + security headers.
  - `FILES_UPSTREAM_ALLOWED_HOSTS`: optional allowlist for proxy upstream hostnames.
  - `FILES_PROXY_MAX_BYTES`: max bytes proxied from upstream file servers.
  - `EXCEL_COMPILE_MAX_BYTES=10485760`: max upload size for Excel Compile.
  - `UPLOAD_PACK_MAX_ZIP_MB=500`: max ZIP size for Upload Pack.
  - `UPLOAD_PACK_MAX_FILE_MB=200`: max single file size for Upload Pack/extra uploads.
  - `UPLOAD_PACK_MAX_FILES=5000`: max file count inside a pack.
  - `EXTRA_FILES_ALLOWED=true`: enable/disable associated file uploads.
  - `APP_TIMEZONE`: default timezone (IANA name) for docpack timestamps if no admin override is set.
  - `BRANDING_LOGO_MAX_BYTES`: max logo upload size in bytes (default 2097152).
  - `TINYMRP_SEED_ADMIN=true`: opt-in admin seeding on first boot (compat mode).
  - `TINYMRP_ADMIN_EMAIL`, `TINYMRP_ADMIN_PASSWORD`: credentials used when seeding.

Examples: `.env.dev.example`, `.env.docker.example`, `.env.server.example`.

---

## Security Modes

- **compat (default)**: backward-compatible behavior, with safer CORS defaults, origin-based CSRF guard for session APIs, and warnings for weak secrets. If secrets are missing/weak, TinyMRP generates a temporary runtime secret (sessions/tokens will reset on restart).
- **strict**: /api is token-only, CORS is disabled unless `TINYMRP_ALLOWED_ORIGINS` is set, cookies are Secure + SameSite=Strict, and startup fails if secrets are missing/weak.

See `SECURITY.md` for the full threat model and `MIGRATION.md` for a safe rollout checklist.

### Runtime secrets (compat mode)

If `SECRET_KEY`/`SECURITY_PASSWORD_SALT` are missing or empty in compat mode, the app persists them to:

```
instance/runtime_secrets.json
```

Set explicit secrets in production to avoid warning logs and to support strict mode.

## Admin Settings

- `/admin/settings` lets admins upload a branding logo (PNG/SVG) and set the default timezone used in document packs.

## Upload Pack + Associated Files

- UI: `/ui/upload-pack` (requires `import.bom` permission).
- ZIP structure:
  - `bom/` with `*_FLATBOM.txt` and `*_TREEBOM.txt`
  - `deliverables/<group>/...`
  - `extra/<PN>/<REV_OR__no_rev__>/...`
- If revision is blank, use the `__no_rev__` token in paths; DB stores revision as an empty string.
- `*_FLATBOM.txt` supports **either** JSON-per-line **or** Python dict-literal-per-line (single quotes). Import skips malformed/non-dict lines and reports them as errors.
- `*_TREEBOM.txt` is tab-separated; rows with blank PART NUMBER are skipped with warnings.
- BOM import is **best-effort**: it continues past bad lines/rows and returns an error/warning report in the UI (downloadable as JSON).

API endpoints:

- `POST /api/upload/pack` (multipart `file` plus optional `dry_run`, `strict_structure`)
- `GET /api/parts/<pn>/<rev>/extra`
- `POST /api/parts/<pn>/<rev>/extra`
- `DELETE /api/parts/<pn>/<rev>/extra/<file_id>`

## Help System

- Help content lives in `docs/help/` (markdown).
- Generate the static help page with: `flask help build`.
- The output is written to `app/static/help/help.html` and `app/static/help/help_toc.json`.
- Commit the generated files so `/help` is always up to date.

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
- BOM text files are written as UTF-8 **without** a BOM; the TinyMRP importer tolerates UTF-8 BOM (`utf-8-sig`) for legacy files.
- Publish/BOM includes "Manage associated files..." and an optional "Create Upload Pack (ZIP)" toggle.
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

## Business Modules (Jobs, Suppliers, Customers, Orders)

Server-rendered admin screens live under:

- `/admin/jobs`
- `/admin/suppliers`
- `/admin/customers`
- `/admin/orders`

REST APIs for integration and automation:

- `GET|POST /api/jobs`, `GET|PUT|DELETE /api/jobs/<job_number>`, `PATCH /api/jobs/<job_number>/status`
- `GET|POST /api/suppliers`, `GET|PUT /api/suppliers/<code>`, `PATCH /api/suppliers/<code>/status`
- `GET|POST /api/customers`, `GET|PUT /api/customers/<code>`, `POST /api/customers/<code>/shipping-addresses`
- `GET|POST /api/orders`, `GET|PUT|DELETE /api/orders/<order_number>`, `PATCH /api/orders/<order_number>/status`

All endpoints require authentication and respect role permissions (`jobs.*`, `suppliers.*`, `customers.*`, `orders.*`).

---

## Roles & Permissions

Default roles and permissions are created/updated by:

```powershell
flask --app run.py user seed-roles
```

This overwrites descriptions and permission lists for the built-in roles below.

### Built-in roles (default permissions)

- `admin`: full access (all permissions).
- `planner`:
  - `items.view`, `bom.view`, `mrp.run`, `reports.view`
  - `jobs.view`, `jobs.manage`, `orders.view`, `orders.manage`
  - `suppliers.view`, `customers.view`
  - `tools.view`, `import.bom`
- `operator`:
  - `workorders.view`, `workorders.edit`, `workorders.close`
  - `inventory.issue`, `inventory.receive`
  - `items.view`, `bom.view`
  - `tools.view`, `import.bom`
- `viewer` (read-only):
  - `items.view`, `bom.view`, `workorders.view`, `reports.view`
  - `jobs.view`, `orders.view`, `suppliers.view`, `customers.view`
- `customer_viewer` (scoped read-only):
  - `items.view`, `bom.view`, `jobs.view`, `orders.view`, `customers.view`
- `supplier_viewer` (scoped read-only):
  - `items.view`, `bom.view`, `orders.view`, `suppliers.view`

Roles can be managed by admins in `/admin/roles`. If roles are corrupted, re-run `seed-roles` to restore defaults.

### Row-level scoping for external users

External users are scoped to the customers/suppliers they are linked to. This is enforced server-side for:

- Jobs list/detail
- Orders list/detail
- Customers/Suppliers list/detail
- Parts inventory listing and part detail

Rules:

- **Customer-scoped users** (linked via `Customer.users`) only see their customers, jobs, and orders (including orders tied to their jobs).
- **Supplier-scoped users** (linked via `Supplier.users`) only see their suppliers, orders, and jobs associated via vendor/order links.
- **Viewer role with links**: a user with role `viewer` who is linked to any customer/supplier is treated as scoped (prevents accidental global access).
- **Internal roles** (`admin`, `operator`, `planner`) remain unscoped.

To link a user, edit the Customer/Supplier in the admin UI and add the user under its `users` field.

Optional override (not recommended in production):

- `ACL_ENFORCED=false` disables row-level scoping.

---

## Quick Start (local dev)

PowerShell snippet (from `handycommands.txt`):

```powershell
# 1) (optional) Run nginx in front of Flask for protected file offload
$env:FILES_LOCAL_ROOT = "C:/CADEXPORT"
docker run --rm -d --name tinymrp-nginx-dev -p 5001:80 `
  -v "${PWD}/docker/nginx/nginx.dev.conf:/etc/nginx/nginx.conf:ro" `
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

Visit http://localhost:5000 (app). Files are served via `/files/view/<token>` after login.

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

### One-folder (Windows) quick start

If you want a turnkey setup where the only input is the host **deliverables folder**, use:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\run-tinymrp-container.ps1 "C:\TinyMRP\Deliverables"
```

This persists everything under:

- `<deliverables>\.tinymrp\mongo` (MongoDB data)
- `<deliverables>\.tinymrp\instance` (runtime secrets)

### Post-start maintenance

After the helper script finishes, re-use the generated env file for follow-up commands:

```powershell
docker compose --env-file C:\CADEXPORT\.tinymrp\compose.env -f C:\TinyMRP\Server\tinymrp_v2\docker-compose.onefolder.yml logs -n 200 app
docker compose --env-file C:\CADEXPORT\.tinymrp\compose.env -f C:\TinyMRP\Server\tinymrp_v2\docker-compose.onefolder.yml ps
curl http://localhost:5000/
```

To stop the stack:

```powershell
docker compose --env-file C:\CADEXPORT\.tinymrp\compose.env -f C:\TinyMRP\Server\tinymrp_v2\docker-compose.onefolder.yml down
```

### User and role management

The first run seeds default roles plus an admin user (`admin@example.com`). Check the generated password in the `logs -n 200 app` output and log into `http://localhost:5000/` with it.

For CLI management once the stack is up, run:

```powershell
docker compose --env-file C:\CADEXPORT\.tinymrp\compose.env -f C:\TinyMRP\Server\tinymrp_v2\docker-compose.onefolder.yml exec app flask --app run.py user list
docker compose --env-file C:\CADEXPORT\.tinymrp\compose.env -f C:\TinyMRP\Server\tinymrp_v2\docker-compose.onefolder.yml exec app flask --app run.py role list
docker compose --env-file C:\CADEXPORT\.tinymrp\compose.env -f C:\TinyMRP\Server\tinymrp_v2\docker-compose.onefolder.yml exec app flask --app run.py user create --email new@local --password Secret123
docker compose --env-file C:\CADEXPORT\.tinymrp\compose.env -f C:\TinyMRP\Server\tinymrp_v2\docker-compose.onefolder.yml exec app flask --app run.py user grant-role --email new@local --role admin
```

Use the same `docker compose exec ...` pattern to run `user set-password`, `grant-role`, or `revoke-role`.

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
- Set strong `SECRET_KEY` and `SECURITY_PASSWORD_SALT`.
- If these are left empty in compat mode, TinyMRP will generate and persist them to `instance/runtime_secrets.json`.
- Optional first-run admin seed: `TINYMRP_SEED_ADMIN=true`, `TINYMRP_ADMIN_EMAIL`, `TINYMRP_ADMIN_PASSWORD`.

5) Build and start

```bash
sudo docker compose up -d --build
docker compose ps
```

6) Test

- App: `http://YOUR_SERVER_IP/` (or `http://YOUR_SERVER_IP:<HTTP_PORT>`)
- Files: served through the app with `/files/view/<token>` (no public listing).
- First login: only if you enabled `TINYMRP_SEED_ADMIN=true`; use `TINYMRP_ADMIN_EMAIL`/`TINYMRP_ADMIN_PASSWORD` (or the one-time password logged on first boot in compat mode).

### Recovery CLI (user/role management)

```powershell
# List users and roles
flask --app run.py user list
flask --app run.py role list

# Reset password
flask --app run.py user set-password --email user@example.com

# Grant/revoke roles
flask --app run.py user grant-role --email user@example.com --role admin
flask --app run.py user revoke-role --email user@example.com --role viewer

# Bootstrap a new admin (creates user if missing)
flask --app run.py user bootstrap-admin --email admin@example.com --password ChangeMe123!
```

Docker usage:

```bash
docker compose exec app flask --app run.py user list
```

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
- Nginx protected paths:
  - `docker/nginx/nginx.conf` exposes an internal `/__files/` location for X-Accel-Redirect and protects `/deliverables/` with `auth_request`.
- Frontend file base:
  - `frontend/.env.production` should be empty unless you intentionally enable `FILES_PUBLIC_URLS=true`.

### First-Run Seeding

On first boot, the app always seeds built-in roles. Admin users are only created if you opt in with:

- `TINYMRP_SEED_ADMIN=true`
- `TINYMRP_ADMIN_EMAIL`
- `TINYMRP_ADMIN_PASSWORD` (or a one-time generated password in compat mode)

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
- `/ui/upload-pack` - Upload Pack (ZIP import of BOM + deliverables + associated files).

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
  "binder_add_hardware_summary": true,
  "binder_page_numbers": true,
  "output_name": "ASM-1001_A_docpack",
  "stamp_quote": false, "stamp_confidential": false, "stamp_approved": false,
  "stamp_wip": false, "stamp_inprogress": false
}
```

Behavior highlights:

- Visual Summary is listed first in the index, then the root (father) and children.
- Cover page is page 1 (page numbers overlaid skip the cover when enabled).
- Excel BOM includes thumbnails, hyperlinks to the app, and normalized attributes.
- Output filenames include a timestamp suffix and are capped to a Windows-safe length.

---

## CLI Utilities

User management:

- `flask --app run.py user seed-roles`
- `flask --app run.py user create --email <email> --password <pw>`
- `flask --app run.py user grant-admin --email <email>`
- Role-combo test users (creates every role combination):
  - `flask --app run.py user seed-combos --prefix testuser --domain example.test`
  - `flask --app run.py user seed-combos --password Test1234!`

Data helpers (see `app/cli.py`):

- Demo parts/BOM: `flask --app run.py user seed-parts`, `flask --app run.py user seed-bom`.
- Large demo dataset (parts + BOM tree):
  - `flask --app run.py data seed-demo --scale small|medium|large`
  - `flask --app run.py data clear-demo`
- Business data (suppliers, customers, jobs, orders):
  - `flask --app run.py biz seed`
  - `flask --app run.py biz clear`
- Importer: `flask --app run.py importcmd zip --file <path>.zip`.
- File discovery: `flask --app run.py files scan-one --pn PN --rev REV`.
- Thumbnails:
  - `flask --app run.py thumbs rebuild-one --pn PN --rev REV`
  - `flask --app run.py thumbs rebuild-all`
- Attributes backfill:
  - `flask --app run.py attrs backfill`

---

## Notes & Tips

- CSRF is enabled; some API blueprints are explicitly exempted where required for SPA calls.
- Session-authenticated API requests are protected by an origin/referer CSRF guard; strict mode makes `/api/*` token-only.
- Files config uses canonical keys `FILES_LOCAL_ROOT`, `FILES_URL_PREFIX`, `FILES_UPSTREAM_BASE`. Backward-compatible aliases `FILE_ROOT_LOCAL` and `FILE_ROOT_HTTP` remain for older code paths.
- Frontend build artifacts are written to `app/static/parts-ui` by `npm run build` from the `frontend` directory.

---

## License

This repository inherits the spirit of the original TinyMRP project. Add your license here if distributing.
