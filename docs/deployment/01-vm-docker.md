# 01 — TinyMRP on a VM or server with Docker

The recommended way to run one TinyMRP instance. It works the same on a
Proxmox/VMware/Hyper-V guest, a cloud VM, a spare desktop, or Windows Docker
Desktop, because everything runs in the same Linux containers.

**Nextcloud is not involved anywhere on this page.** This stack is TinyMRP,
MongoDB and Redis, and nothing else.

- [What you get](#what-you-get)
- [Requirements](#requirements)
- [Step 1 — Prepare the VM](#step-1--prepare-the-vm)
- [Step 2 — Install Docker](#step-2--install-docker)
- [Step 3 — Get TinyMRP](#step-3--get-tinymrp)
- [Step 4 — Choose an access mode](#step-4--choose-an-access-mode)
- [Step 5 — Run the installer](#step-5--run-the-installer)
- [Step 6 — Open the firewall](#step-6--open-the-firewall)
- [Step 7 — First login and sample data](#step-7--first-login-and-sample-data)
- [Step 8 — Start on boot](#step-8--start-on-boot)
- [Everything the installer asks and accepts](#everything-the-installer-asks-and-accepts)
- [Everything the installer writes](#everything-the-installer-writes)
- [Day-to-day commands](#day-to-day-commands)
- [Customising the deployment](#customising-the-deployment)
- [Unattended installs](#unattended-installs)
- [Windows Docker Desktop](#windows-docker-desktop)
- [If something goes wrong](#if-something-goes-wrong)

---

## What you get

| Container | Role | Reachable from |
| --- | --- | --- |
| `app` | TinyMRP (gunicorn) | The host port you choose |
| `mongo` | Application database, authentication enabled | Only the other containers |
| `redis` | Shared rate-limit counters | Only the other containers |
| `caddy` | Reverse proxy + automatic HTTPS. **Only in `domain` mode.** | Ports 80/443 |

Mongo and Redis publish no host ports at all. The `app` container runs with a
read-only root filesystem, all Linux capabilities dropped, and
`no-new-privileges`. The only writable path is your deliverables folder.

---

## Requirements

| | Minimum | Comfortable |
| --- | --- | --- |
| vCPU | 2 | 4 |
| RAM | 4 GB | 8 GB |
| Disk (system) | 20 GB | 40 GB |
| Disk (deliverables) | as large as your CAD exports | plus 30% for thumbnails |
| OS | Ubuntu 22.04/24.04, Debian 12, or any distro with Docker Engine 24+ | Ubuntu 24.04 LTS |

The deliverables folder can be a separate disk or an NFS/SMB mount, as long as
it is mounted before Docker starts and the container user (UID 1000) can write
to it.

---

## Step 1 — Prepare the VM

```bash
sudo apt-get update && sudo apt-get -y upgrade
sudo apt-get install -y git curl openssl
sudo timedatectl set-timezone Australia/Sydney   # use your own zone
```

Give the VM a fixed address. TinyMRP is reached by IP or hostname, and a DHCP
lease that moves will change the URL out from under your users.

```bash
# Netplan example: /etc/netplan/01-tinymrp.yaml
network:
  version: 2
  ethernets:
    ens18:
      dhcp4: false
      addresses: [192.168.1.50/24]
      routes: [{ to: default, via: 192.168.1.1 }]
      nameservers: { addresses: [192.168.1.1, 1.1.1.1] }
```

```bash
sudo netplan apply
ip -4 addr show scope global | grep inet     # confirm the address
```

Create the deliverables folder. It does not have to be under `/srv`, but it
must be on a filesystem with room to grow:

```bash
sudo mkdir -p /srv/tinymrp/deliverables
sudo chown -R 1000:1000 /srv/tinymrp/deliverables
```

> **Why UID 1000?** The app container runs as UID 1000 and writes thumbnails,
> uploads and extra files into this tree. The installer will chown an *empty*
> folder for you, but it deliberately refuses to touch a folder that already
> has contents — see [If something goes wrong](#if-something-goes-wrong).

---

## Step 2 — Install Docker

Use Docker's own repository. Distribution packages are often too old for
Compose v2.

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"      # then log out and back in
```

Verify, as the user who will run the installer:

```bash
docker --version              # 24.0 or newer
docker compose version        # v2.x — "docker-compose" v1 will not work
docker info >/dev/null && echo "daemon OK"
```

---

## Step 3 — Get TinyMRP

**Option A — clone the repository** (works with no published image; builds
locally):

```bash
sudo mkdir -p /opt && cd /opt
sudo git clone https://github.com/<your-org>/tinymrp_v2.git
sudo chown -R "$USER":"$USER" /opt/tinymrp_v2
cd /opt/tinymrp_v2
chmod +x deploy/community/install.sh deploy/community/tinymrp.sh
```

**Option B — download a release bundle** (no build step; needs access to the
published image):

```bash
cd /opt
curl -LO https://github.com/<your-org>/tinymrp_v2/releases/download/v2.0.0/tinymrp-community-v2.0.0.tar.gz
tar -xzf tinymrp-community-v2.0.0.tar.gz
cd tinymrp-community-v2.0.0
chmod +x install.sh tinymrp.sh
```

A release bundle carries `release.env`, which pins the image repository and the
exact version. A clone does not, which is why Option A needs `--build`.

---

## Step 4 — Choose an access mode

| Mode | Binds | URL users type | TLS | Choose when |
| --- | --- | --- | --- | --- |
| `localhost` | `127.0.0.1` only | `http://localhost:5000` | none | Evaluating on the machine itself |
| `lan` | `0.0.0.0` | `http://192.168.1.50:5000` | none | An office/workshop network you trust |
| `domain` | Caddy owns 80/443 | `https://tinymrp.example.com` | automatic Let's Encrypt | Anything reachable from the internet |

`lan` mode sends passwords and session cookies over the network **in clear
text**. That is a deliberate, supported choice for a private network, and the
app logs a warning about it on every start. It is not acceptable for anything
internet-facing. To keep a LAN deployment but add TLS, see
[Adding HTTPS to a LAN deployment](08-networking-and-tls.md#adding-https-to-a-lan-deployment).

`domain` mode needs a public DNS `A` record pointing at this host **before you
run the installer**, plus inbound 80 and 443 — Let's Encrypt validates over
port 80.

---

## Step 5 — Run the installer

From a clone:

```bash
./deploy/community/install.sh --build --with-demo-data
```

From a release bundle:

```bash
./install.sh --with-demo-data
```

Drop `--with-demo-data` if you are loading real data straight away; it creates
real demo logins.

The installer asks four things:

```
Deliverables folder [/home/you/TinyMRP/Deliverables]: /srv/tinymrp/deliverables
Access mode (localhost/lan/domain) [localhost]: lan
TinyMRP localhost port [5000]: 5000
LAN hostname or IP shown to users [192.168.1.50]: 192.168.1.50
Administrator email [admin@example.com]: admin@yourcompany.com
Administrator password (14+ characters): ********************
```

Then it:

1. checks Docker, Compose and that the port is free;
2. creates the deliverables folder and chowns it to `1000:1000` if it is empty;
3. generates the Mongo root password, the scoped Mongo application password,
   `SECRET_KEY` and `SECURITY_PASSWORD_SALT` — 32 random bytes each;
4. builds the image (`--build`) or pulls the pinned release image;
5. starts Mongo, Redis and the app, and waits for all three to report healthy;
6. creates the first administrator from the credentials you typed;
7. **erases the administrator password from `.env`** and recreates the app
   container without it, so the one-time secret does not persist;
8. installs the sample dataset if you passed `--with-demo-data`;
9. prints the URL, the administrator address and, if requested, the demo
   passwords.

Expect 5–15 minutes for the first `--build` (it compiles the frontend and
installs Python wheels) and under a minute afterwards.

Success looks like:

```
TinyMRP Community is ready at http://192.168.1.50:5000
Administrator: admin@yourcompany.com
```

---

## Step 6 — Open the firewall

`lan` mode binds `0.0.0.0`, but the host firewall still has to allow it.

```bash
# ufw (Ubuntu)
sudo ufw allow from 192.168.1.0/24 to any port 5000 proto tcp comment 'TinyMRP LAN'
sudo ufw status verbose

# firewalld (RHEL/Rocky)
sudo firewall-cmd --permanent --zone=internal --add-port=5000/tcp
sudo firewall-cmd --permanent --zone=internal --add-source=192.168.1.0/24
sudo firewall-cmd --reload
```

Restrict the source range. Allowing 5000 from anywhere on a VM with a public
interface publishes a plain-HTTP login form to the internet.

For `domain` mode open 80 and 443 instead, and leave 5000 closed — the app is
published only on loopback there and Caddy is the front door.

Check from another machine:

```bash
curl -sS http://192.168.1.50:5000/api/health
# {"ok": true, "service": "tinymrp", ...}
```

---

## Step 7 — First login and sample data

Open the URL and sign in with the administrator address and the password you
typed. Change it under **Account → Password** immediately.

If you passed `--with-demo-data`, the installer printed one login per role
scenario. Those passwords are shown once. To install (or reinstall) the dataset
later:

```bash
cd /opt/tinymrp_v2/deploy/community
docker compose --env-file .env -f compose.yaml exec -T app \
  flask --app run.py demo install
```

And to remove the demo logins before real data arrives:

```bash
docker compose --env-file .env -f compose.yaml exec -T app \
  flask --app run.py demo remove --disable
```

Full detail — what the standard roles are, what the sample dataset contains,
how to create real users — is in [06 — First run](06-first-run.md).

---

## Step 8 — Start on boot

Every container is declared `restart: unless-stopped`, so Docker restarts the
stack after a reboot on its own. Confirm rather than assume:

```bash
sudo reboot
# after it comes back
cd /opt/tinymrp_v2/deploy/community && ./tinymrp.sh status
```

If you stopped the stack deliberately with `./tinymrp.sh stop`, Docker honours
that across reboots. Start it again with `./tinymrp.sh start`.

To have the stack come up even if someone ran `docker compose down`, add a
systemd unit:

```ini
# /etc/systemd/system/tinymrp-stack.service
[Unit]
Description=TinyMRP container stack
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/tinymrp_v2/deploy/community
ExecStart=/usr/bin/docker compose --env-file .env -f compose.yaml up -d --wait
ExecStop=/usr/bin/docker compose --env-file .env -f compose.yaml stop
User=youruser

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tinymrp-stack
systemctl status tinymrp-stack
```

Add `--profile domain` to both `ExecStart` and `ExecStop` if you installed in
`domain` mode.

---

## Everything the installer asks and accepts

### Flags

| Flag | Effect |
| --- | --- |
| `--build` | Build the app image from this checkout instead of pulling a published one. Tags it `tinymrp-local:<VERSION>-src.<git-sha>` and sets the pull mode to `never`. |
| `--with-demo-data` | After the first start, install the CV03 sample dataset and one demo login per role, printing the passwords once. |
| `--help` | Print usage and exit. |

### Environment variables (all optional)

| Variable | Default | Meaning |
| --- | --- | --- |
| `TINYMRP_NON_INTERACTIVE` | `0` | `1` reads every answer from the variables below instead of prompting. |
| `TINYMRP_DELIVERABLES_PATH` | prompted | Host folder for deliverables. Required when non-interactive. |
| `TINYMRP_ACCESS_MODE` | `localhost` | `localhost`, `lan`, or `domain`. |
| `TINYMRP_APP_PORT` | `5000` | Host port for `localhost`/`lan` modes. |
| `TINYMRP_LAN_HOST` | prompted | IP or hostname users will type. Required for non-interactive `lan`. |
| `TINYMRP_DOMAIN` | prompted | Public FQDN. Required for non-interactive `domain`. |
| `ACME_EMAIL` | prompted | Let's Encrypt contact. Required for non-interactive `domain`. |
| `TINYMRP_ADMIN_EMAIL` | prompted | First administrator. Required when non-interactive. |
| `TINYMRP_ADMIN_PASSWORD` | prompted | 14+ characters. Required when non-interactive. Erased from `.env` after bootstrap. |
| `TINYMRP_IMAGE_REPOSITORY` | `release.env`, or `tinymrp-local` with `--build` | Image to run. |
| `TINYMRP_VERSION` | `release.env`, or derived with `--build` | Must be semver; `latest` is rejected. |
| `TINYMRP_INSTALL_PULL` | `always`, or `never` with `--build` | `always`, `missing`, or `never`. |
| `TINYMRP_BUILD_FROM_SOURCE` | `0` | `1` is the same as `--build`. |
| `TINYMRP_INSTALL_DEMO_DATA` | `0` | `1` is the same as `--with-demo-data`. |
| `WEB_CONCURRENCY` | auto | Gunicorn workers. See [Customising](#tuning-worker-count-and-memory). |

### Refusals

The installer stops rather than guess when: `.env` already exists; Docker is
absent or its daemon is down; Compose v2 is missing; the port is in use; the
administrator password is under 14 characters; the email has no `@x.y`; the
version is not semver; a value contains a quote, backslash, `$` or newline
(those would corrupt the generated `.env`); or `domain` mode finds 80/443 busy.

---

## Everything the installer writes

`deploy/community/.env`, mode `0600`:

| Key | Example | Notes |
| --- | --- | --- |
| `COMPOSE_PROJECT_NAME` | `tinymrp-community` | Docker resource prefix. |
| `TINYMRP_IMAGE_REPOSITORY` / `TINYMRP_VERSION` | `tinymrp-local` / `2.0.0-src.c8375c6` | The exact image. |
| `ACCESS_MODE` | `lan` | Read by `tinymrp.sh` to decide the Caddy profile. |
| `APP_BIND_IP` / `APP_PORT` | `0.0.0.0` / `5000` | Host publish address. |
| **`TINYMRP_URL`** | `http://192.168.1.50:5000` | **The address users type.** Its scheme drives the cookie and CSP posture — do not edit it without also changing the mode and port. |
| `TINYMRP_TRUSTED_PROXY_HOPS` | `0` (`lan`/`localhost`), `1` (`domain`) | How many `X-Forwarded-*` hops to believe. |
| `TINYMRP_ALLOWED_ORIGINS` | `http://192.168.1.50:5000` | CORS allowlist; defaults to `TINYMRP_URL`. |
| `DELIVERABLES_PATH` | `/srv/tinymrp/deliverables` | Bind-mounted at `/data/deliverables`. |
| `MONGO_DB`, `MONGO_ROOT_USER`, `MONGO_ROOT_PASSWORD`, `MONGO_APP_USER`, `MONGO_APP_PASSWORD` | generated | The app connects as the scoped user, never root. |
| `SECRET_KEY`, `SECURITY_PASSWORD_SALT` | generated | 32 random bytes each. **Changing these invalidates every session and signed file link.** |
| `TINYMRP_SEED_ADMIN` | `false` after install | Left `false` so restarts never re-seed. |
| `TINYMRP_ADMIN_EMAIL` / `TINYMRP_ADMIN_PASSWORD` | address / **empty** | The password is erased once the account exists. |
| `BACKUP_KEEP_DAYS`, `BACKUP_KEEP_COUNT`, `BACKUP_MAX_TOTAL_GB` | `14`, `8`, `10` | Backup retention. |
| `TINYMRP_DOMAIN`, `ACME_EMAIL`, `CADDY_BIND_IP` | domain mode only | Caddy configuration. |

Back this file up separately from the database. Without `SECRET_KEY` and the
Mongo credentials, a database backup cannot be restored into a working
instance.

---

## Day-to-day commands

All from `deploy/community/` (or the extracted bundle):

```bash
./tinymrp.sh status                       # container health
./tinymrp.sh logs                         # follow the last 200 lines
./tinymrp.sh logs 1000                    # follow the last 1000
./tinymrp.sh stop                         # stop; data is untouched
./tinymrp.sh start                        # start again
./tinymrp.sh backup                       # verified Mongo dump + config
./tinymrp.sh backup --include-deliverables
./tinymrp.sh restore backups/2026-08-14T02-00-00Z
./tinymrp.sh restore backups/<dir> --include-deliverables --yes
./tinymrp.sh update v2.1.0                # backs up first, rolls back on failure
./tinymrp.sh uninstall                    # remove containers, keep all data
./tinymrp.sh uninstall --delete-data --yes  # also delete Docker volumes
```

`uninstall` never deletes your deliverables folder or your backups, with or
without `--delete-data`.

Raw Compose access, when you need it:

```bash
cd deploy/community
docker compose --env-file .env -f compose.yaml ps
docker compose --env-file .env -f compose.yaml logs -f app
docker compose --env-file .env -f compose.yaml exec -T app flask --app run.py user list
```

More detail in [10 — Backups, updates and uninstall](10-operations.md).

---

## Customising the deployment

### Changing the address or port after installation

```bash
cd deploy/community
./tinymrp.sh stop
# edit .env: APP_PORT, TINYMRP_URL, TINYMRP_ALLOWED_ORIGINS must all agree
nano .env
./tinymrp.sh start
```

Changing `APP_PORT` without changing `TINYMRP_URL` produces the login loop
described in [07 — Troubleshooting](07-troubleshooting.md#i-log-in-and-land-back-on-the-login-page).

### Moving from `lan` to `domain`

1. Point a public DNS `A` record at the host and wait for it to resolve.
2. Stop the stack: `./tinymrp.sh stop`.
3. In `.env` set `ACCESS_MODE="domain"`, `APP_BIND_IP="127.0.0.1"`,
   `TINYMRP_DOMAIN="tinymrp.example.com"`, `ACME_EMAIL="you@example.com"`,
   `TINYMRP_URL="https://tinymrp.example.com"`,
   `TINYMRP_ALLOWED_ORIGINS="https://tinymrp.example.com"`, and
   `TINYMRP_TRUSTED_PROXY_HOPS="1"`.
4. `docker compose --env-file .env -f compose.yaml --profile domain up -d --wait`

### Tuning worker count and memory

The entrypoint picks `cores + 1` workers, floored at 2 and capped at 6. Each
worker is a Python process with its own Mongo connection pool — budget roughly
250–400 MB each. On a small VM, or one running other services, pin it:

```bash
# in .env
WEB_CONCURRENCY="2"
```

then `docker compose --env-file .env -f compose.yaml up -d --force-recreate app`.

### Upload size limits

Defaults: 1024 MB per zip, 1024 MB per file, 5000 files per pack. To change,
add to `.env` and recreate the app container:

```bash
UPLOAD_PACK_MAX_ZIP_MB="2048"
UPLOAD_PACK_MAX_FILE_MB="2048"
UPLOAD_PACK_MAX_FILES="10000"
TINYMRP_MAX_CONTENT_MB="2048"
```

`TINYMRP_MAX_CONTENT_MB` is the hard request cap and defaults to
`min(UPLOAD_PACK_MAX_ZIP_MB, 200)`, so raising only the pack limits will still
give you HTTP 413. In `domain` mode Caddy streams the body with no extra limit;
if you put your own nginx in front, raise `client_max_body_size` to match.

### Logging

```bash
LOG_LEVEL="INFO"      # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT="text"     # or json, for log aggregation
```

Every other setting is in
[05 — Configuration reference](05-configuration-reference.md).

---

## Unattended installs

For an image build, Ansible, or CI:

```bash
export TINYMRP_NON_INTERACTIVE=1
export TINYMRP_DELIVERABLES_PATH=/srv/tinymrp/deliverables
export TINYMRP_ACCESS_MODE=lan
export TINYMRP_LAN_HOST=192.168.1.50
export TINYMRP_APP_PORT=5000
export TINYMRP_ADMIN_EMAIL=admin@yourcompany.com
export TINYMRP_ADMIN_PASSWORD="$(openssl rand -base64 24)"
echo "Administrator password: $TINYMRP_ADMIN_PASSWORD"

mkdir -p "$TINYMRP_DELIVERABLES_PATH"
./deploy/community/install.sh --build
```

Print or store the password before the run: the installer erases it from `.env`
once the account exists, and nothing can recover it afterwards. If you lose it:

```bash
docker compose --env-file deploy/community/.env -f deploy/community/compose.yaml \
  exec -T app flask --app run.py user set-password --email admin@yourcompany.com
```

This exact flow (minus `--build`) is exercised by the
`community-compose-smoke` GitHub Actions workflow on every change to the
installer, the compose file, or the app.

---

## Windows Docker Desktop

The same containers, driven by PowerShell:

```powershell
cd C:\TinyMRP\Server\tinymrp_v2\deploy\community
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Build -WithDemoData
```

Parameters mirror the Linux flags:

| Parameter | Meaning |
| --- | --- |
| `-DeliverablesPath C:\TinyMRP\Deliverables` | Host folder for deliverables. |
| `-AccessMode localhost\|lan\|domain` | As above. |
| `-Address 192.168.1.50` | LAN address or public domain. |
| `-Port 5000` | Host port. |
| `-AdminEmail admin@yourcompany.com` | First administrator. |
| `-Build` | Build from this checkout. |
| `-WithDemoData` | Install the evaluation dataset. |

In `lan` mode the script offers to add a Windows Firewall rule scoped to
**Private** networks only, and never adds one without asking. Run PowerShell as
Administrator if you accept.

Two Windows-specific notes:

- Docker Desktop must have **File Sharing** enabled for the drive holding the
  deliverables folder, or the bind mount fails at start.
- Use forward slashes or a plain drive path; the installer normalises it.

Operations use `.\tinymrp.ps1` with the same verbs as `tinymrp.sh`.

If Docker Desktop is not available to you, use
[03 — Windows LAN](03-windows-lan.md) instead, which runs the app as a native
Windows service.

---

## If something goes wrong

Start with the log:

```bash
cd deploy/community
docker compose --env-file .env -f compose.yaml logs --tail 100 app
```

| Symptom | Cause | Fix |
| --- | --- | --- |
| Login succeeds then returns to the login page | `TINYMRP_URL` scheme does not match how you are reaching the site | See [07 — Troubleshooting](07-troubleshooting.md#i-log-in-and-land-back-on-the-login-page) |
| `WARNING: ... is not owned by uid 1000 and is not empty` | Existing deliverables folder | `sudo chown -R 1000:1000 /srv/tinymrp/deliverables` |
| `ERROR: deliverables root ... is NOT writable` | Same, or a read-only mount | As above; check the mount options |
| `Set an explicit semantic TINYMRP_VERSION` | Clone without `release.env` | Add `--build` |
| `TCP port 5000 is already in use` | Something else has it | `sudo ss -ltnp | grep :5000`, then pick another port |
| `.env already exists` | Previous installation | Use `./tinymrp.sh`, or move `.env` aside to start over |
| App container restarts forever | Mongo credentials mismatched against an existing volume | `docker compose ... logs mongo`; a mid-life credential change needs [UPDATING_PRODUCTION.md](../UPDATING_PRODUCTION.md) |
| Reachable locally, not from another PC | Host firewall, or `localhost` mode | [Step 6](#step-6--open-the-firewall); check `APP_BIND_IP` is `0.0.0.0` |

The complete symptom list is in [07 — Troubleshooting](07-troubleshooting.md).
