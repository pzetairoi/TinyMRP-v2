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
  - `FILES_ACCEL_REDIRECT_PREFIX`: optional internal Nginx location used for `X-Accel-Redirect`; leave this empty for the guided Caddy deployment and any setup that does not create and verify a matching internal route.
  - `FILES_ALLOW_LEGACY_TOKENS=false`: allow legacy base64 file tokens (off by default).
- Optional:
  - `TINYMRP_SECURITY_MODE=compat|strict`: security profile (default compat).
  - `TINYMRP_ALLOWED_ORIGINS`: comma-separated CORS allowlist (strict mode requires this).
  - `TINYMRP_CORS_CREDENTIALS=true`: allow credentials when using an explicit allowlist.
  - `API_TOKEN_DEFAULT_TTL_DAYS=90`: lifetime applied to newly created API tokens.
  - `API_TOKEN_MAX_TTL_DAYS=365`: maximum lifetime users may request; must be at least the default.
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
  - `/ui/addin/tokens` to create, rotate and revoke expiring API tokens (secrets are shown once).
  - `/ui/admin/addin` for admins (per-token/global revocation + scheme preset flags).
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
- `GET /api/me/tokens`, `POST /api/me/tokens`, `POST /api/me/tokens/<id>/rotate`, `DELETE /api/me/tokens/<id>`
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

Missing canonical roles are created without overwriting local customisations by:

```powershell
flask --app run.py user seed-roles
```

Use `user seed-roles --dry-run` to report drift. Use `--apply` only after review
when you intentionally want to restore the canonical definitions.

### Built-in roles (default permissions)

- `administrator`: all registered permissions.
- `security_administrator`: users, roles, assignments, token revocation and audit.
- `engineering_manager`, `engineering`: engineering data and workflows.
- `commercial`: sales, procurement, customer, supplier and job workflows.
- `internal`, `workshop`: internal read/collaboration and workshop execution.
- `customer`, `supplier`: deliberately scoped external read-only access.
- `auditor`: broad read-only audit and business visibility.

The exact permission intent is documented in
`docs/security/role_intent_feature_matrix.md`. Roles can be managed by authorised
administrators in `/admin/roles`. The legacy `admin` slug remains recognised for
existing installations but is not created for new users.

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
- **Internal canonical roles** remain unscoped unless their role definition is
  deliberately mapped to a business scope.

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
flask --app run.py user bootstrap-admin --email admin@example.com

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

### Windows service deployment (LAN-only, no Docker)

For secured office environments that do not allow Docker Desktop, use the native Windows guide:

- `deploy/windows/README.md`
- `deploy/windows/IT_REQUEST_TEMPLATE.md`

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

On the first run, the PowerShell helper generates a strong administrator password,
writes the bootstrap settings to `<deliverables>\.tinymrp\compose.env`, and shows
the password once in the invoking terminal. It is never printed by the container.
Log into `http://localhost:5000/` with the displayed email and password.

For CLI management once the stack is up, run:

```powershell
docker compose --env-file C:\CADEXPORT\.tinymrp\compose.env -f C:\TinyMRP\Server\tinymrp_v2\docker-compose.onefolder.yml exec app flask --app run.py user list
docker compose --env-file C:\CADEXPORT\.tinymrp\compose.env -f C:\TinyMRP\Server\tinymrp_v2\docker-compose.onefolder.yml exec app flask --app run.py role list
docker compose --env-file C:\CADEXPORT\.tinymrp\compose.env -f C:\TinyMRP\Server\tinymrp_v2\docker-compose.onefolder.yml exec app flask --app run.py user create --email new@example.com
docker compose --env-file C:\CADEXPORT\.tinymrp\compose.env -f C:\TinyMRP\Server\tinymrp_v2\docker-compose.onefolder.yml exec app flask --app run.py user grant-role --email new@example.com --role internal
```

Use the same `docker compose exec ...` pattern to run `user set-password`, `grant-role`, or `revoke-role`.

Useful snippets (from `handycommands.txt`):

```bash
docker compose up -d
docker compose exec app flask --app run.py user seed-roles
docker compose exec app flask --app run.py user bootstrap-admin --email admin@example.com

# Recreate just the app container
docker compose up -d --force-recreate app
```

---

## Guided Host Deployment (Ubuntu + Caddy)

The recommended production path is now the guided multi-instance deployment under [`deploy/README.md`](deploy/README.md).

Default behavior:

- Caddy is the shared reverse proxy on ports `80` and `443`.
- Caddy obtains and renews HTTPS certificates automatically.
- Each TinyMRP instance gets its own private Docker network and MongoDB container.
- MongoDB is never published on the host.
- DNS guidance and validation are built into the scripts.
- Protected deliverables stay on the normal TinyMRP app route, so `FILES_ACCEL_REDIRECT_PREFIX` is empty by default.

Typical flow:

```bash
sudo ./deploy/scripts/install-host.sh --base-domain tinymrp.com
sudo ./deploy/scripts/create-instance.sh company1 company1.tinymrp.com
sudo ./deploy/scripts/install-nextcloud-instance.sh company1 cloud.company1.tinymrp.com
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --read-only --non-interactive
sudo ./deploy/scripts/doctor.sh
```

Update and rollback commands for that deployment path live in [`deploy/README.md`](deploy/README.md):

- `sudo ./deploy/scripts/update-repo.sh`
- `sudo ./deploy/scripts/update-instance.sh company1`
- `sudo ./deploy/scripts/update-all-instances.sh`
- `sudo ./deploy/scripts/rollback-instance.sh company1`

Minimal operator input:

- `install-host.sh`
  - ACME email
  - optional base domain
- `create-instance.sh`
  - instance name
  - final public domain
- `install-nextcloud-instance.sh`
  - TinyMRP instance name
  - final per-company Nextcloud domain
- `install-nextcloud.sh`
  - legacy shared/global Nextcloud domain
- `scan-nextcloud-instance.sh`
  - run an immediate Nextcloud rescan for one linked TinyMRP instance
- `install-nextcloud-scan-job.sh`
  - install or update the recurring scan job that keeps Nextcloud in sync with server-side TinyMRP imports
- `link-nextcloud-instance.sh`
  - deployed TinyMRP instance name
  - optional `--nextcloud-instance <name|global>` override
  - read-only or bidirectional access mode, unless you pass a flag

Nextcloud integration stays deployment-side. The recommended multi-company path is one Nextcloud per TinyMRP company under `/srv/tinymrp/nextcloud/<instance>`. TinyMRP keeps ownership of `/srv/tinymrp/instances/<instance>/deliverables`, and `link-nextcloud-instance.sh` now defaults to the same-name Nextcloud instance while prompting for either read-only sharing mode or bidirectional sync mode. Read-only stays the safest default and mounts deliverables under `/mnt/tinymrp-deliverables/<instance>` without write access. Bidirectional mode is available for trusted internal workflows that need desktop-client uploads or sync back into the VPS deliverables folder. The link flow now also runs an immediate Nextcloud scan and installs a recurring scan job by default so TinyMRP server-side imports propagate back out to Nextcloud desktop clients by refreshing both the external storage cache and the user-visible mount paths. The default Caddy deployment continues to rely on `FILES_ACCEL_REDIRECT_PREFIX=""`.

Useful commands:

```bash
sudo ./deploy/scripts/link-nextcloud-instance.sh company1
sudo ./deploy/scripts/install-nextcloud-instance.sh company1 cloud.company1.tinymrp.com
sudo ./deploy/scripts/scan-nextcloud-instance.sh company1
sudo ./deploy/scripts/install-nextcloud-scan-job.sh company1 --interval-minutes 5
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --read-only
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --bidirectional
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --non-interactive --read-only
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --non-interactive --bidirectional
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --scan-now-only --read-only --non-interactive
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --nextcloud-instance global --read-only --non-interactive
```

`--non-interactive` requires either `--read-only` or `--bidirectional`.

DNS examples:

- `company1.tinymrp.com` -> `A company1 <server-ip>`
- `tinymrp.customercompany.com` -> `A tinymrp <server-ip>`
- `customercompany.com` -> `A @ <server-ip>`
- `cloud.tinymrp.com` -> `A cloud <server-ip>`

For full DNS examples, local VM mode, and Nextcloud details, see [`deploy/README.md`](deploy/README.md).

### Legacy Single-Stack Compose Path

The repo still includes the original single-stack Compose setup in `docker-compose.yml` (`mongo`, `app`, `nginx`). Keep using that only if you want the older manual, single-instance deployment shape.

Quick notes for that legacy path:

- `HTTP_PORT` maps the host port to the internal `nginx` container on port `80`.
- `DELIVERABLES_DIR` is bind-mounted into both `app` and `nginx` at `/data/deliverables`.
- `FILES_LOCAL_ROOT=/data/deliverables` and `FILES_URL_PREFIX=/deliverables` stay the expected app-side values.
- `docker/nginx/nginx.conf` still includes the protected `/deliverables` and optional `X-Accel-Redirect` paths.
- Keep `FILES_ACCEL_REDIRECT_PREFIX` empty unless you intentionally enable and validate a matching Nginx internal route such as `"/__files"`.

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
