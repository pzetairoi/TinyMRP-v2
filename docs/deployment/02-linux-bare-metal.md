# 02 — TinyMRP on Linux without Docker

A native install: MongoDB from the distribution repositories, TinyMRP under
gunicorn as a hardened systemd service, nginx in front. Use it where Docker is
not permitted, or where you already run MongoDB.

If Docker is available, [01 — VM / server with Docker](01-vm-docker.md) is
easier to install and to update.

**No Nextcloud anywhere on this page.**

- [What gets installed where](#what-gets-installed-where)
- [Requirements](#requirements)
- [Guided install](#guided-install)
- [Install options](#install-options)
- [Manual install](#manual-install)
- [Verify](#verify)
- [First login and sample data](#first-login-and-sample-data)
- [Operating the service](#operating-the-service)
- [Updating](#updating)
- [Backups](#backups)
- [Customising](#customising)

---

## What gets installed where

| Path | Contents |
| --- | --- |
| `/opt/tinymrp_v2` | Application code (rsynced from your checkout) |
| `/opt/tinymrp_venv` | Python virtualenv |
| `/etc/tinymrp/.env` | Configuration and secrets, `0640 root:tinymrp` |
| `/srv/tinymrp/deliverables` | Deliverables root (configurable) |
| `/etc/systemd/system/tinymrp.service` | The service unit |
| `/etc/nginx/sites-available/tinymrp` | Reverse proxy |

The service runs as the system user `tinymrp`, with `ProtectSystem=strict`,
every Linux capability dropped, a `@system-service` syscall filter, and only
two writable paths: the deliverables root and `/opt/tinymrp_v2/instance`.

---

## Requirements

- Ubuntu 22.04/24.04 or Debian 12 (the installer uses `apt`)
- 2 vCPU, 4 GB RAM minimum
- root via `sudo`
- Python 3.11 or 3.12
- Outbound internet for packages, or a local mirror

Node.js is **not** required: the compiled frontend is committed to the
repository. You only need it if you change the frontend sources.

---

## Guided install

```bash
sudo apt-get update && sudo apt-get install -y git
sudo git clone https://github.com/<your-org>/tinymrp_v2.git /usr/local/src/tinymrp_v2
cd /usr/local/src/tinymrp_v2
```

### LAN, plain HTTP

```bash
sudo ./deploy/scripts/install-server.sh \
  --http-only \
  --url http://192.168.1.50 \
  --deliverables /srv/tinymrp/deliverables \
  --admin-email admin@yourcompany.com
```

`--url` is what users type. Its scheme is what tells TinyMRP whether to mark
session cookies `Secure`; with `--http-only` it must be `http://` or the
installer refuses. Omit it and the installer uses `--domain`, or the host's
first LAN address with a warning.

### Public domain with Let's Encrypt

```bash
sudo ./deploy/scripts/install-server.sh \
  --domain tinymrp.example.com \
  --certbot \
  --admin-email admin@yourcompany.com \
  --with-fail2ban
```

DNS must already point at this host and port 80 must be reachable — certbot
validates over it.

### Internal CA certificate

```bash
sudo ./deploy/scripts/install-server.sh \
  --domain tinymrp.corp.local \
  --cert /etc/ssl/corp/tinymrp.crt \
  --key  /etc/ssl/corp/tinymrp.key
```

### Self-signed (lab, or behind a VPN)

```bash
sudo ./deploy/scripts/install-server.sh --domain tinymrp.lan --self-signed
```

Every client — including SolidWorks add-in machines — must trust the
certificate or the connection is refused.

The installer prints the URL, the environment file path, and the one-time
administrator password when `--admin-email` was given.

---

## Install options

| Option | Default | Meaning |
| --- | --- | --- |
| `--domain <fqdn>` | — | Server name for nginx and TLS. Required for every TLS mode. |
| `--url <url>` | derived | The address users type, scheme included. Required for `--http-only` without `--domain`. |
| `--deliverables <dir>` | `/srv/tinymrp/deliverables` | Deliverables root. |
| `--mongo-uri <uri>` | installs MongoDB 7.0 locally | Point at an existing database and skip the install. |
| `--certbot` | — | Obtain a Let's Encrypt certificate. |
| `--self-signed` | — | Generate a 825-day self-signed certificate. |
| `--cert <file> --key <file>` | — | Use existing certificates. |
| `--http-only` | — | No TLS. Trusted networks only. |
| `--with-fail2ban` | off | Install fail2ban with the TinyMRP login jail. |
| `--skip-ufw` | off | Do not touch the firewall. |
| `--admin-email <email>` | — | Seed the first administrator and print a generated password once. |
| `--yes` | off | Non-interactive; accept defaults. |

`--compat` was removed with compat security mode; the script exits with an
explanation if you pass it.

The installer is idempotent. Re-running it syncs new code, keeps the existing
`/etc/tinymrp/.env` untouched, and keeps existing certificates.

---

## Manual install

If you would rather not run the script, this is what it does.

```bash
# 1. Packages
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip nginx curl openssl rsync

# 2. MongoDB 7.0 (skip if you have one)
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc \
  | sudo gpg --dearmor --yes -o /usr/share/keyrings/mongodb-server-7.0.gpg
. /etc/os-release
echo "deb [signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] https://repo.mongodb.org/apt/ubuntu ${VERSION_CODENAME}/mongodb-org/7.0 multiverse" \
  | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt-get update && sudo apt-get install -y mongodb-org
sudo systemctl enable --now mongod

# 3. Service user and code
sudo useradd --system --home-dir /opt/tinymrp_v2 --shell /usr/sbin/nologin tinymrp
sudo mkdir -p /opt/tinymrp_v2 /srv/tinymrp/deliverables
sudo rsync -a --delete --exclude '.git' --exclude '.venv' \
  --exclude 'frontend/node_modules' --exclude 'tests' \
  /usr/local/src/tinymrp_v2/ /opt/tinymrp_v2/
sudo chown -R tinymrp:tinymrp /opt/tinymrp_v2 /srv/tinymrp/deliverables

# 4. Virtualenv
sudo python3 -m venv /opt/tinymrp_venv
sudo /opt/tinymrp_venv/bin/pip install --upgrade pip
sudo /opt/tinymrp_venv/bin/pip install -r /opt/tinymrp_v2/requirements.txt
sudo chown -R tinymrp:tinymrp /opt/tinymrp_venv

# 5. Configuration
sudo mkdir -p /etc/tinymrp
sudo cp /opt/tinymrp_v2/.env.server.example /etc/tinymrp/.env
sudo nano /etc/tinymrp/.env          # set TINYMRP_URL, FILES_LOCAL_ROOT, both secrets
sudo chmod 0640 /etc/tinymrp/.env
sudo chown root:tinymrp /etc/tinymrp/.env

# 6. systemd
sudo cp /opt/tinymrp_v2/deploy/tinymrp.service /etc/systemd/system/tinymrp.service
sudo systemctl daemon-reload
sudo systemctl enable --now tinymrp

# 7. nginx
sudo cp /opt/tinymrp_v2/deploy/nginx.server.conf /etc/nginx/sites-available/tinymrp
sudo ln -sf /etc/nginx/sites-available/tinymrp /etc/nginx/sites-enabled/tinymrp
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Generate the secrets with `openssl rand -hex 32` — two different values.

The minimum `/etc/tinymrp/.env`:

```bash
TINYMRP_URL=http://192.168.1.50
TINYMRP_TRUSTED_PROXY_HOPS=1
MONGO_URI=mongodb://127.0.0.1:27017/tinymrp-v2
FILES_LOCAL_ROOT=/srv/tinymrp/deliverables
FILES_URL_PREFIX=/Deliverables
SECRET_KEY=<32+ random characters>
SECURITY_PASSWORD_SALT=<a different 32+ random characters>
```

`TINYMRP_TRUSTED_PROXY_HOPS=1` because nginx is in front. Set `0` only if you
expose gunicorn on 8000 directly, which the shipped unit does not.

---

## Verify

```bash
sudo systemctl status tinymrp
sudo journalctl -u tinymrp -n 50 --no-pager

# the app, behind nginx
curl -sS http://127.0.0.1:8000/api/health
curl -sS http://127.0.0.1:8000/api/ready

# through nginx
curl -sS http://192.168.1.50/api/health

# gunicorn must NOT be exposed to the network
sudo ss -ltnp | grep 8000     # expect 127.0.0.1:8000 only
```

The startup log tells you the transport it resolved:

```
Browser transport: plain HTTP (TINYMRP_URL=http://192.168.1.50)
```

If that says HTTPS while you browse over plain HTTP, fix `TINYMRP_URL` — see
[07 — Troubleshooting](07-troubleshooting.md#i-log-in-and-land-back-on-the-login-page).

---

## First login and sample data

```bash
# create or repair the administrator
cd /opt/tinymrp_v2
sudo -u tinymrp ENV_FILE=/etc/tinymrp/.env \
  /opt/tinymrp_venv/bin/flask --app app user bootstrap-admin --email admin@yourcompany.com

# install the evaluation dataset and demo logins
sudo -u tinymrp ENV_FILE=/etc/tinymrp/.env \
  /opt/tinymrp_venv/bin/flask --app app demo install
```

Details in [06 — First run](06-first-run.md).

---

## Operating the service

```bash
sudo systemctl start|stop|restart tinymrp
sudo systemctl status tinymrp
sudo journalctl -u tinymrp -f
sudo journalctl -u tinymrp --since "1 hour ago" --no-pager
sudo systemctl reload nginx
sudo nginx -t
```

Any environment change needs `sudo systemctl restart tinymrp`; the file is read
once at start.

---

## Updating

```bash
cd /usr/local/src/tinymrp_v2
sudo git fetch --tags && sudo git checkout v2.1.0

# back up first
mongodump --uri="mongodb://127.0.0.1:27017/tinymrp-v2" \
  --archive=/var/backups/tinymrp-$(date -u +%FT%TZ).gz --gzip
sudo cp /etc/tinymrp/.env /var/backups/tinymrp-env-$(date -u +%F).bak

# re-run the installer: it syncs code and keeps your .env and certificates
sudo ./deploy/scripts/install-server.sh --domain tinymrp.example.com --certbot

sudo systemctl status tinymrp
curl -sS http://127.0.0.1:8000/api/health
```

See [docs/UPDATING_PRODUCTION.md](../UPDATING_PRODUCTION.md) for the
version-to-version notes.

---

## Backups

Three things must be captured together, or a restore will not produce a working
instance:

```bash
#!/usr/bin/env bash
# /usr/local/bin/tinymrp-backup.sh
set -euo pipefail
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="/var/backups/tinymrp/$STAMP"
mkdir -p "$DEST"

# 1. database
mongodump --uri="mongodb://127.0.0.1:27017/tinymrp-v2" \
  --archive="$DEST/mongo.archive.gz" --gzip

# 2. configuration — WITHOUT IT THE SECRETS ARE GONE
install -m 0600 /etc/tinymrp/.env "$DEST/env.bak"

# 3. deliverables
tar -C /srv/tinymrp/deliverables -czf "$DEST/deliverables.tar.gz" .

sha256sum "$DEST"/* > "$DEST/checksums.sha256"
find /var/backups/tinymrp -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +
```

```bash
sudo chmod 0700 /usr/local/bin/tinymrp-backup.sh
sudo crontab -e
# 0 2 * * * /usr/local/bin/tinymrp-backup.sh >> /var/log/tinymrp-backup.log 2>&1
```

Restore:

```bash
sudo systemctl stop tinymrp
mongorestore --uri="mongodb://127.0.0.1:27017" --drop --gzip \
  --archive=/var/backups/tinymrp/<stamp>/mongo.archive.gz
sudo tar -xzf /var/backups/tinymrp/<stamp>/deliverables.tar.gz -C /srv/tinymrp/deliverables
sudo chown -R tinymrp:tinymrp /srv/tinymrp/deliverables
sudo systemctl start tinymrp
```

Restoring a database against a **different** `SECRET_KEY` signs everyone out
and invalidates issued file links. Restoring against a different
`SECURITY_PASSWORD_SALT` invalidates every password. Keep `env.bak`.

---

## Customising

### Worker count

The shipped unit hardcodes `-w 2`, unlike the container which sizes itself.
Edit `ExecStart` in `/etc/systemd/system/tinymrp.service`:

```
ExecStart=/opt/tinymrp_venv/bin/gunicorn -k gthread --threads 4 -w 4 ...
```

then `sudo systemctl daemon-reload && sudo systemctl restart tinymrp`. Budget
250–400 MB per worker.

### Rate limiting across workers

With more than one worker, the in-memory counters are per-process, so the real
budget is multiplied by the worker count. Install Redis and point at it:

```bash
sudo apt-get install -y redis-server
# /etc/tinymrp/.env
RATE_LIMIT_STORAGE_URI=redis://127.0.0.1:6379/0
```

### A deliverables root outside /srv

Add it to `ReadWritePaths` in the unit — `ProtectSystem=strict` makes the rest
of the filesystem read-only, so a path that is not listed silently fails to
write:

```
ReadWritePaths=/mnt/cad/deliverables /opt/tinymrp_v2/instance
```

### Upload limits

Raise the app caps **and** nginx together:

```bash
# /etc/tinymrp/.env
UPLOAD_PACK_MAX_ZIP_MB=2048
TINYMRP_MAX_CONTENT_MB=2048
```

```nginx
# in the server block
client_max_body_size 2048m;
```

### fail2ban

```bash
sudo ./deploy/scripts/install-server.sh --with-fail2ban ...   # or by hand:
sudo cp deploy/server/fail2ban-filter-tinymrp-login.conf /etc/fail2ban/filter.d/tinymrp-login.conf
sudo cp deploy/server/fail2ban-jail-tinymrp.local /etc/fail2ban/jail.d/tinymrp.local
sudo systemctl enable --now fail2ban
sudo fail2ban-client status tinymrp-login
```

Every remaining setting is in
[05 — Configuration reference](05-configuration-reference.md).
