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

- Backend: Python 3.11, Flask 3.x, MongoEngine 0.29.x, PyMongo 4.x.
- DB: MongoDB 6/7 (local or Atlas).
- Frontend: React 19, Vite 7, PrimeReact, ThreeJS (3MF viewer).
- Dev: `python-dotenv`, Docker Compose, optional Nginx for secure file offload.

---

## Configuration

Three settings decide whether a deployment works; everything else has a working
default or is generated for you.

| | Setting | Example |
| --- | --- | --- |
| 1 | `FILES_LOCAL_ROOT` — where deliverables live | `/srv/tinymrp/deliverables` |
| 2 | `TINYMRP_URL` — the address users type, **scheme included** | `https://mrp.example.com` |
| 3 | `MONGO_URI` | `mongodb://localhost:27017/tinymrp-v2` |

`SECRET_KEY` and `SECURITY_PASSWORD_SALT` are mandatory and are generated for
you by every installer. The application refuses to start without them rather
than inventing its own, because a key it invented cannot tell a forged session
from a real one after a restart.

**Every variable, its default and when to change it:**
[`docs/deployment/05-configuration-reference.md`](docs/deployment/05-configuration-reference.md).
That page is the single source of truth — this list is deliberately not a
second copy of it.

Templates: `.env.dev.example`, `.env.docker.example`, `.env.server.example`.

---

## Security Model

There is one model. The same-origin browser uses its authenticated session plus
an origin/referer CSRF check; integrations and the SolidWorks add-in use bearer
tokens. `/api/auth/check` is bearer-only, public-share APIs require their scoped
share capability, and `/api/health` is anonymous. Browser-only APIs reject
bearer substitution. CORS is disabled unless an origin is explicitly allowed,
cookies are Secure + SameSite=Strict, and startup fails if secrets are missing
or weak.

There is no relaxed compatibility profile. Local HTTP uses the same
authentication model with an explicit local origin and operator-supplied
secrets; the application never invents a signing key.

See `SECURITY.md` for the full threat model and
`docs/security/supply_chain_policy.md` for immutable pin updates and
release-gate evidence.

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

- Repository Markdown files are the single documentation source. The `/help`
  UI publishes an explicit allowlist of user guidance, installation/operations
  material and approved product information; day-to-day user guidance is the
  default. Developer, security and history material remains repository-only.
- Generate the static help page with: `flask help build`.
- The output is written to `app/static/help/help.html` and `app/static/help/help_toc.json`.
- Contextual `?` links use `app/static/help/context_help.json` to connect each
  authenticated UI area to its applicable user-guide section.
- Maintainer guidance lives in [`docs/development/`](docs/development/), and
  concise evidence routing lives in [`docs/history/`](docs/history/).
- Commit the generated files so `/help` is always up to date.

## SolidWorks Add-in

A task pane add-in for SolidWorks that drives publish/BOM exports, the tools,
and part numbering. The project lives in [`solidworks-addin/`](solidworks-addin/).

| You want to | Read |
| --- | --- |
| **Install a released build** | [`docs/help/03_addin_installation.md`](docs/help/03_addin_installation.md) — the same text the app shows under Help |
| **Build, register, configure or package it** | [`solidworks-addin/README.md`](solidworks-addin/README.md) — requirements, MSBuild, RegAsm, every `TinyMRP_config.txt` setting, the Inno Setup installer, and what Publish/BOM writes |
| **Connect it to a server** | Create an API token at `/ui/addin/tokens`, then Configuration → Quick Start in the task pane |

Set the backend URL **with its scheme** (`https://mrp.company.local`). Without
one the add-in assumes HTTPS for anything that is not genuine loopback.

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
existing installations only as an ordinary custom role; its name grants no
permissions and it is not created for new users.

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

PowerShell development example:

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

## Deployment

Step-by-step guides for every option live in
[`docs/deployment/`](docs/deployment/README.md), written to be read on GitHub
before you have a server. **That directory is the single source of truth for
installing TinyMRP**; the sections below cover only the developer and legacy
paths that have no guide of their own.

| You have | Guide |
| --- | --- |
| A Linux VM or server with Docker — **recommended** | [01 — VM / server with Docker](docs/deployment/01-vm-docker.md) |
| Anything else — bare metal, Windows LAN, restricted Windows, multi-instance VPS, local dev | [Choosing a path](docs/deployment/README.md) |

Only three things need configuring: the deliverables folder, the address users
type (`TINYMRP_URL`, **scheme included**), and optionally the port. Secrets,
database credentials and reverse-proxy configuration are generated for you.

Nextcloud is optional and exists only on the VPS path. Every other deployment
ignores it entirely.

---

## TinyMRP Community (standalone Docker)

For a single workstation, VM or small server. From a clone of this repository:

```bash
./deploy/community/install.sh --build --with-demo-data
```

**The complete walkthrough — prerequisites, every question the installer asks,
firewall, TLS, first login, day-to-day operation and every failure mode — is
[`docs/deployment/01-vm-docker.md`](docs/deployment/01-vm-docker.md).** That is
the single source of truth for this path; the paragraphs below are orientation
only and deliberately do not restate it.

Or download the versioned Community bundle from the matching GitHub release:

- Linux: `tinymrp-community-vX.Y.Z.tar.gz`, then run `./install.sh`.
- Windows Docker Desktop: `tinymrp-community-vX.Y.Z.zip`, then run
  `install.cmd`.

Both platforms use the same `deploy/community/compose.yaml`, the same hardened
Linux application image, authenticated MongoDB, and internal-only Redis. The
default URL is `http://localhost:5000`; LAN exposure is an explicit choice and
domain/TLS mode is an optional Caddy profile. Nextcloud is not included.

Use the bundled `tinymrp.sh` or `tinymrp.ps1` for start, stop, status, logs,
`reconfigure` (change address, port or access mode without hand-editing
`.env`), version-pinned update with rollback, verified backup/restore, and
uninstall that preserves data by default. Do not install with a remote
`curl | sh` or `irm | iex` pipeline, and do not configure an installed system
with the mutable `latest` tag.

Lifecycle guarantees and current host acceptance status are in
[`deploy/community/ACCEPTANCE.md`](deploy/community/ACCEPTANCE.md).

## Developer Docker Compose

```bash
docker compose up --build
```

### One-folder (Windows) quick start

If you want a turnkey setup where the only input is the host **deliverables folder**, use:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\run-tinymrp-container.ps1 "C:\TinyMRP\Deliverables"
```

This localhost/LAN-only helper intentionally persists
to the internet. Use the guided VPS/Caddy deployment for strict authentication,
Secure cookies and TLS.

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

Useful administration commands:

```bash
docker compose up -d
docker compose exec app flask --app run.py user seed-roles
docker compose exec app flask --app run.py user bootstrap-admin --email admin@example.com

# Recreate just the app container
docker compose up -d --force-recreate app
```

---

## Guided multi-instance VPS (Ubuntu + Caddy)

One shared Caddy proxy with automatic HTTPS, one isolated TinyMRP instance per
company. Use it when a single host serves several customers.

```bash
sudo ./deploy/scripts/install-host.sh --acme-email ops@example.com --base-domain example.com
sudo ./deploy/scripts/create-instance.sh company1 company1.example.com
sudo ./deploy/scripts/doctor.sh
```

- Orientation and the questions each script asks:
  [docs/deployment/04-vps-multi-instance.md](docs/deployment/04-vps-multi-instance.md)
- Operational reference for the scripts themselves, including Nextcloud:
  [deploy/README.md](deploy/README.md)

Nextcloud is **optional** and installed only by the scripts with `nextcloud` in
their name.

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

Builds into `app/static/parts-ui` (manifest included); the Flask routes under
`/ui/*` read that manifest to inject the JS and CSS. **The compiled output is
committed**, so deploying TinyMRP needs no Node.js — only working on the
frontend does.

Scripts, dev server and the build/commit rule:
[`frontend/README.md`](frontend/README.md).

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
- Session-authenticated API requests are protected by an origin/referer CSRF guard. In strict mode, browser APIs require the same-origin session, integration APIs accept or require bearer tokens according to their explicit endpoint policy, and public-share APIs validate only their scoped share capability.
- Files config uses canonical keys `FILES_LOCAL_ROOT`, `FILES_URL_PREFIX`, `FILES_UPSTREAM_BASE`. Backward-compatible aliases `FILE_ROOT_LOCAL` and `FILE_ROOT_HTTP` remain for older code paths.
- Frontend build artifacts are written to `app/static/parts-ui` by `npm run build` from the `frontend` directory.

---

## License

[The Unlicense](LICENSE) — released into the public domain. Copy, modify,
publish, use, compile, sell or distribute it, commercially or not, by any
means. There is no warranty of any kind.

Operational support terms are deployment-specific and are not defined by this
repository's public-domain software licence.
