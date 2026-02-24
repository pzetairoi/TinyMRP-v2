# Server And Web App Installation

This page covers first deployment, safe updates, and operating basics for TinyMRP v2.

## Deployment Options

### Recommended: Docker Compose

Use Docker for production or pilot environments. It is the easiest path for repeatable updates.

### Hardened Windows LAN-Only (No Docker)

Use this when IT requires a Windows workstation deployment with internal-only access.

- Guide: `deploy/windows/README.md`
- IT ticket template: `deploy/windows/IT_REQUEST_TEMPLATE.md`
- Hardened env template: `deploy/windows/.env.windows.lan.example`

### Advanced: Local developer runtime

Use direct Python and Node only for development and debugging.

## Prerequisites

- Access to a host with Docker and Docker Compose.
- MongoDB connection string (`MONGO_URI`), local or hosted.
- A file root where deliverables are stored and readable by the app.
- Access to edit environment variables and run CLI commands.

## First-Time Setup (Docker)

### 1) Prepare environment file

- Copy an example such as `.env.server.example` to `.env`.
- Set at least:
  - `SECRET_KEY`
  - `SECURITY_PASSWORD_SALT`
  - `MONGO_URI`
  - `FILES_LOCAL_ROOT` (or equivalent file root key in your setup)
  - `HTTP_PORT`

### 2) Start the stack

Run from repository root:

```powershell
docker compose up -d --build
```

### 3) Seed roles and create first admin

```powershell
docker compose exec app flask --app run.py user seed-roles
docker compose exec app flask --app run.py user create --email admin@yourcompany.com --password <password>
docker compose exec app flask --app run.py user grant-admin --email admin@yourcompany.com
```

### 4) Open TinyMRP

- URL: `http://<server>:<HTTP_PORT>`
- Login with the admin account.

## Windows LAN-Only Setup (No Docker)

Use this path for service-based Windows deployment with NGINX reverse proxy + Waitress.

1. Follow `deploy/windows/README.md` step-by-step.
2. Keep Flask app private on `127.0.0.1:8000`.
3. Keep MongoDB private on `127.0.0.1:27017` (or separate internal DB server).
4. Expose only NGINX HTTP (`80`) to allowed LAN ranges.
5. Run with `TINYMRP_SECURITY_MODE=compat`, `FORCE_HTTPS=false`, `FILES_PUBLIC_URLS=false`.

Compatibility note (as of 2026-02-24):

- Windows 10 support ended on 2025-10-14.
- MongoDB current Windows support tables list Windows 11 / Windows Server variants for modern releases.
- NGINX on Windows has known limitations and does not run as a native Windows service without a wrapper.
- If host OS must stay Windows 10, prefer running MongoDB on a separate supported host and point `MONGO_URI` there.

## File Storage Rules

TinyMRP matches files by part number and revision. Standard groups include:

- `pdf`, `dxf`, `step`, `edr`, `3mf`, `ply`, `stl`, `png`, `datasheet`

Expected naming pattern:

- `PARTNUMBER_REV_REVISION.ext`
- Drawing preview PNG commonly appears as `*_DWG.png`.

If revision is blank, empty revision tokens are allowed and should be treated as valid.

## Upload Pack Limits

Global defaults can be controlled by env and admin settings:

- Max ZIP size
- Max single file size
- Max files per ZIP

These limits are enforced during `/api/upload/pack` processing.

## Local Development (Advanced)

1. Install Python dependencies: `pip install -r requirements.txt`
2. Install frontend dependencies in `frontend/`: `npm install`
3. Run backend (`python run.py`) and build frontend (`npm run build` or `npm run dev`)

## Upgrade Procedure

1. Pull latest code.
2. Rebuild and restart containers:

```powershell
docker compose up -d --build
```

3. Re-run `seed-roles` only if role definitions were intentionally updated by release notes.
4. Validate critical pages:
  - `/ui/parts`
  - `/ui/part/<pn>`
  - `/ui/upload-pack`
  - `/admin/jobs/`
  - `/admin/orders/`

## Backup Recommendations

- Database backup (MongoDB dump/snapshot).
- Deliverables file root backup.
- `instance/` backup if used for runtime files.
- Branding and app settings backup.

## Security Baseline

- Keep `SECRET_KEY` and `SECURITY_PASSWORD_SALT` strong and private.
- Run HTTPS in production.
- Keep `FILES_PUBLIC_URLS` disabled unless you explicitly need public file links.
- Use roles and permissions instead of code edits for access control.

## Help Build Command

After updating help markdown:

```powershell
flask --app run.py help build
```

This regenerates:

- `app/static/help/help.html`
- `app/static/help/help_toc.json`
