# Server And Web App Installation

This page covers first deployment, safe updates, and operating basics for TinyMRP v2.

## Deployment Options

### Recommended: Guided Ubuntu deployment

Use the guided Linux deployment scripts for production and pilot environments. This path uses:

- Docker for the app containers
- Caddy as the public reverse proxy
- automatic HTTPS certificate management
- private MongoDB containers
- built-in DNS guidance and DNS validation
- TinyMRP app file serving for protected deliverables by default

Main guide:

- `deploy/README.md`

Main commands:

```bash
sudo ./deploy/scripts/install-host.sh --base-domain tinymrp.com
sudo ./deploy/scripts/create-instance.sh company1 company1.tinymrp.com
sudo ./deploy/scripts/doctor.sh
```

### Hardened Windows LAN-Only (No Docker)

Use this when IT requires a Windows workstation deployment with internal-only access.

- Guide: `deploy/windows/README.md`
- IT ticket template: `deploy/windows/IT_REQUEST_TEMPLATE.md`
- Hardened env template: `deploy/windows/.env.windows.lan.example`

### Advanced: Local developer runtime

Use direct Python and Node only for development and debugging.

## Prerequisites

- Ubuntu host with internet access on ports `80` and `443`.
- A domain or subdomain you can point to the server.
- Access to edit DNS records at your DNS provider.
- `sudo` access on the host.

## First-Time Setup (Guided Ubuntu)

### 1) Install host services

```bash
sudo ./deploy/scripts/install-host.sh --base-domain tinymrp.com
```

This stores host config in `/srv/tinymrp/host/.env` and starts the shared Caddy reverse proxy.

### 2) Create an instance

```bash
sudo ./deploy/scripts/create-instance.sh company1 company1.tinymrp.com
```

The script:

- detects the public IP
- prints the exact DNS record to create
- waits for DNS to resolve correctly
- creates the app and private MongoDB containers
- creates the Caddy route
- enables HTTPS automatically for public domains

Generated file-serving defaults for guided Caddy deployments:

- `FILES_LOCAL_ROOT="/data/deliverables"`
- `FILES_URL_PREFIX="/deliverables"`
- `FILES_PUBLIC_URLS="false"`
- `FILES_ACCEL_REDIRECT_PREFIX=""`

Keep the deliverables bind mount at `/srv/tinymrp/instances/<instance>/deliverables:/data/deliverables`. Do not set `FILES_ACCEL_REDIRECT_PREFIX="/__files"` for Caddy unless you explicitly implement and validate a Caddy-compatible protected static offload flow.

### 3) Open TinyMRP

- URL: `https://company1.tinymrp.com`
- Login with the generated admin account from the installer output.

## DNS And Domain Setup

Examples:

- `company1.tinymrp.com` -> `A company1 <server-ip>`
- `tinymrp.customercompany.com` -> `A tinymrp <server-ip>`
- `customercompany.com` -> `A @ <server-ip>`
- `cloud.tinymrp.com` -> `A cloud <server-ip>`

If the host has IPv6, the scripts also print an optional `AAAA` record.

## Nextcloud

Use the matching installer for a public Nextcloud domain:

```bash
sudo ./deploy/scripts/install-nextcloud.sh cloud.tinymrp.com
```

## Deliverables Smoke Test

After importing a small Upload Pack with files under `deliverables/png` and `deliverables/pdf`, verify:

1. Files exist on the host under `/srv/tinymrp/instances/<instance>/deliverables`.
2. The app container sees them under `/data/deliverables`.
3. TinyMRP can display or download them through the normal `/deliverables` route.
4. The default Caddy deployment is not relying on a `"/__files"` redirect.

## Recover A Broken Caddy Instance

If an existing Caddy deployment still has `FILES_ACCEL_REDIRECT_PREFIX="/__files"`, run:

```bash
cd /srv/tinymrp/instances/<instance>
sudo cp .env ".env.bak.$(date +%Y%m%d-%H%M%S)"
sudo sed -i 's#^FILES_ACCEL_REDIRECT_PREFIX=.*#FILES_ACCEL_REDIRECT_PREFIX=""#' .env
sudo docker compose up -d --force-recreate
```

## Local VM Mode

For local-only testing:

```bash
sudo ./deploy/scripts/install-host.sh --local-mode http
sudo ./deploy/scripts/create-instance.sh demo demo.test.local --local-mode http
```

Local domains such as `demo.test.local` and `demo.localhost` do not use public Let's Encrypt certificates.

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
