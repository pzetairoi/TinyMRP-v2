# Installation

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
sudo ./deploy/scripts/install-nextcloud-instance.sh company1 cloud.company1.tinymrp.com
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --read-only --non-interactive
sudo ./deploy/scripts/doctor.sh
```

Operational update commands:

```bash
sudo ./deploy/scripts/update-repo.sh
sudo ./deploy/scripts/update-instance.sh company1
sudo ./deploy/scripts/update-all-instances.sh
sudo ./deploy/scripts/rollback-instance.sh company1
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

The recommended multi-company path is one independent Nextcloud per TinyMRP company instance:

```bash
sudo ./deploy/scripts/install-nextcloud-instance.sh company1 cloud.company1.tinymrp.com
sudo ./deploy/scripts/install-nextcloud-instance.sh company2 cloud.company2.tinymrp.com
```

Then link one or more TinyMRP instances without editing Compose or running `occ` commands by hand:

```bash
sudo ./deploy/scripts/link-nextcloud-instance.sh company1
sudo ./deploy/scripts/link-nextcloud-instance.sh company2 --read-only --non-interactive
```

This keeps TinyMRP as the storage owner. Deliverables stay under `/srv/tinymrp/instances/<instance>/deliverables`, each company Nextcloud lives under `/srv/tinymrp/nextcloud/<instance>/`, the link script writes a managed `compose.tinymrp-deliverables.override.yml` inside that Nextcloud root, and the default Caddy deployment keeps `FILES_ACCEL_REDIRECT_PREFIX=""`.

The link flow now also handles Nextcloud external-storage rescans for server-side TinyMRP file changes:

- it runs an immediate scan after linking
- it installs a recurring scan job by default
- it refreshes both the external-storage cache and the user-visible mount paths
- this keeps TinyMRP import and upload-pack files visible to Nextcloud desktop clients without a manual `occ` scan

The link script now asks which mode to use unless you pass a flag:

- Read-only is the default and safest option. Nextcloud can view, download, and share deliverables, but cannot change them.
- Bidirectional mode is needed for trusted Windows or Mac Nextcloud desktop-client workflows that must upload or sync files back into the VPS deliverables folder.
- Bidirectional mode is higher risk because Nextcloud users can modify or delete TinyMRP deliverables.

Recommended default:

- use read-only for customer sharing and downloads
- use bidirectional only for trusted internal sync workflows

Examples:

```bash
sudo ./deploy/scripts/link-nextcloud-instance.sh company1
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

Legacy shared/global Nextcloud is still available through `install-nextcloud.sh`, but it is not the recommended path for multi-company deployments and it is not re-domained automatically. If you intentionally keep using it, target it with `--nextcloud-instance global`.

Server-side Nextcloud sync smoke test:

1. Create the test folder and file on the host:
   `sudo install -d /srv/tinymrp/instances/<instance>/deliverables/nextcloud-server-side-sync-test`
   `printf 'server-side sync test\n' | sudo tee /srv/tinymrp/instances/<instance>/deliverables/nextcloud-server-side-sync-test/server-created.txt >/dev/null`
2. Run `sudo ./deploy/scripts/scan-nextcloud-instance.sh <instance> --nextcloud-instance <selector>`.
3. Confirm the scan output includes `PASS: User path scan completed for <user>/files/TinyMRP - <instance> Deliverables`.
4. Verify the file appears in the Nextcloud web UI inside `TinyMRP - <instance> Deliverables/nextcloud-server-side-sync-test/server-created.txt`.
5. If a desktop client is connected, verify it downloads the file after the scan job runs or immediately after the manual scan completes.

## Updating And Rollback

Repository update:

```bash
cd /opt/TinyMRP-v2
sudo ./deploy/scripts/update-repo.sh
```

Per-instance update:

```bash
sudo ./deploy/scripts/update-instance.sh company1
```

Batch update:

```bash
sudo ./deploy/scripts/update-all-instances.sh
```

Rollback:

```bash
sudo ./deploy/scripts/rollback-instance.sh company1
```

Per-instance update metadata lives under `/srv/tinymrp/instances/<instance>/updates/`.

Backed up automatically before each update:

- `.env`
- `compose.yml`
- current update state
- the instance Caddy route file if present

Not touched by the normal update flow:

- MongoDB data
- deliverables
- generated secrets

If a release requires a migration, stop after `update-repo.sh`, take a manual MongoDB backup, update one pilot instance first, and only then continue with the rest of the fleet.

To pin one instance to an older tested build:

```bash
sudo ./deploy/scripts/update-instance.sh company1 --image tinymrp-app:abc123def456 --git-commit 0123456789abcdef
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
