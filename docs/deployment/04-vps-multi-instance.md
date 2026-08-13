# 04 — VPS with several instances and automatic HTTPS

The guided multi-tenant path: one Ubuntu host, one shared Caddy reverse proxy,
and one fully isolated TinyMRP instance per company — its own database, its own
deliverables tree, its own domain and certificate.

Use [01 — VM / server with Docker](01-vm-docker.md) instead if you only need
one instance. That path is simpler and self-contained.

- [Architecture](#architecture)
- [Nextcloud is optional](#nextcloud-is-optional)
- [Requirements](#requirements)
- [Step 1 — Install the host services](#step-1--install-the-host-services)
- [Step 2 — Create an instance](#step-2--create-an-instance)
- [Local VM instances without a public domain](#local-vm-instances-without-a-public-domain)
- [Step 3 — Verify](#step-3--verify)
- [Adding more instances](#adding-more-instances)
- [What is written where](#what-is-written-where)
- [Operations](#operations)
- [Capacity](#capacity)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
Internet ─► Caddy (80/443, shared, automatic HTTPS)
              │
              ├─ company1.tinymrp.com ─► tinymrp-company1-app ─► tinymrp-company1-mongo
              │                                                  tinymrp-company1-redis
              └─ company2.tinymrp.com ─► tinymrp-company2-app ─► tinymrp-company2-mongo
                                                                 tinymrp-company2-redis
```

Each instance sits on its own **internal** Docker network plus the shared
`tinymrp_proxy` network. Instances cannot reach each other's databases; only
Caddy can reach their app containers, and only on port 8000.

---

## Nextcloud is optional

**TinyMRP does not depend on Nextcloud in any way.** Everything on this page
works without it, and `create-instance.sh` never installs, configures or
contacts it.

Nextcloud exists here as an *optional* file-sync front end, so an engineering
team can drop CAD exports into a synced folder that TinyMRP then scans. It is
installed by separate, separately-named scripts:

| Script | What it does |
| --- | --- |
| `install-nextcloud.sh` | Shared Nextcloud host services |
| `install-nextcloud-instance.sh` | One Nextcloud per company |
| `link-nextcloud-instance.sh` | Point a TinyMRP instance's deliverables at a Nextcloud folder |
| `scan-nextcloud-instance.sh` | Re-scan a linked folder |
| `install-nextcloud-cron-job.sh`, `install-nextcloud-scan-job.sh` | Schedule the above |

If you never run a script with `nextcloud` in its name, no part of Nextcloud is
installed, and TinyMRP behaves exactly as documented. The deliverables folder is
then an ordinary directory on the host, populated by the SolidWorks add-in,
upload packs, or your own sync tool (rsync, Syncthing, an SMB mount).

`doctor.sh` reports Nextcloud checks as *not applicable* when nothing is
linked.

---

## Requirements

- Ubuntu 22.04 or 24.04 with a public IPv4 address
- 4 GB RAM for the first instance, plus roughly 2 GB per additional instance
- Inbound TCP 80 and 443 from the internet (Let's Encrypt validates over 80)
- A domain whose DNS you can edit
- root via `sudo`

---

## Step 1 — Install the host services

```bash
sudo apt-get update && sudo apt-get install -y git
sudo git clone https://github.com/<your-org>/tinymrp_v2.git /opt/tinymrp-src
cd /opt/tinymrp-src

sudo ./deploy/scripts/install-host.sh \
  --acme-email ops@yourcompany.com \
  --base-domain tinymrp.com
```

This installs Docker Engine and the Compose plugin, `dnsutils`, creates the
shared `tinymrp_proxy` network, starts the shared Caddy container, and writes
host configuration to `/srv/tinymrp/host/.env`.

| Option | Meaning |
| --- | --- |
| `--acme-email you@example.com` | Let's Encrypt contact address. |
| `--base-domain tinymrp.com` | Default parent domain, used for DNS guidance. |
| `--local-mode http\|internal-tls` | Default TLS mode for `.local`/`.test` instance domains. |

Run it once per host. It is idempotent.

---

## Step 2 — Create an instance

```bash
sudo ./deploy/scripts/create-instance.sh company1 company1.tinymrp.com
```

The script:

1. detects the host's public IP and prints the exact DNS record to create;
2. waits for DNS to resolve to this host (skip with `--skip-dns-check`);
3. creates `/srv/tinymrp/instances/company1/` with `deliverables/` and
   `mongo/`, pre-creating every artifact subfolder and chowning to `1000:1000`;
4. generates the Mongo root and scoped application credentials, `SECRET_KEY`
   and `SECURITY_PASSWORD_SALT`;
5. writes the instance `.env` and a rendered `compose.yml`;
6. builds and starts app, Mongo and Redis, and waits for health;
7. installs the Caddy route and validates the whole Caddy config before
   reloading;
8. waits for the public endpoint to answer;
9. prints the URL and the generated administrator credentials **once**.

| Option | Meaning |
| --- | --- |
| `--admin-email admin@company1.com` | First administrator. Defaults to `admin@<domain>`. |
| `--admin-password '<secret>'` | Supply one instead of generating it. |
| `--skip-dns-check` | Do not wait for DNS. Caddy will still fail to get a certificate until DNS is right. |
| `--local-mode http\|internal-tls` | Only for `.local`/`.test`/`.localhost` domains. |

Record the administrator password from the output. It is stored in the
instance `.env`, which is root-readable only.

---

## Local VM instances without a public domain

For an internal VM with no public DNS:

```bash
sudo ./deploy/scripts/create-instance.sh shopfloor shopfloor.test.local --local-mode http
```

A `.local`, `.localhost`, `.test` or `.localdomain` domain is detected
automatically and skips Let's Encrypt. `--local-mode http` serves plain HTTP
through Caddy; `--local-mode internal-tls` uses Caddy's internal CA, which
every client must then trust.

The installer prints the hosts-file entry each workstation needs:

```
192.168.1.50 shopfloor.test.local
```

With `--local-mode http` the instance is written with
`TINYMRP_URL=http://shopfloor.test.local`, so session cookies are not marked
`Secure` and the CSP does not try to upgrade page assets to TLS. That is what
makes a plain-HTTP instance usable — see
[08 — Networking and TLS](08-networking-and-tls.md#why-the-scheme-matters).

> **Upgrading an instance created before `TINYMRP_URL` existed:** the app falls
> back to `INSTANCE_URL`, which every guided instance already has, so an
> existing `--local-mode http` instance gets the right posture from an update
> alone. Re-running `create-instance.sh` writes `TINYMRP_URL` explicitly.

---

## Step 3 — Verify

```bash
sudo ./deploy/scripts/doctor.sh                    # every host and instance check
sudo ./deploy/scripts/doctor.sh --instance company1

curl -sS https://company1.tinymrp.com/api/health
curl -sS https://company1.tinymrp.com/api/ready

docker ps --filter name=tinymrp-company1
```

`doctor.sh` checks Docker, the proxy network, the Caddy file contract, the
rendered routes, container health, routed health endpoints, deliverables
permissions and backup freshness.

Then work through the
[five-minute acceptance test](06-first-run.md#a-five-minute-acceptance-test).

---

## Adding more instances

```bash
sudo ./deploy/scripts/create-instance.sh company2 company2.tinymrp.com
sudo ./deploy/scripts/create-instance.sh acme     tinymrp.acme.com
```

Each gets its own database, deliverables tree, secrets, certificate and admin.
Nothing is shared but Caddy and the Docker daemon.

**Set `WEB_CONCURRENCY` per instance once you have more than two.** The
entrypoint sizes the worker pool from the host's core count on the assumption
that it is the only application present — three instances on a 4-core box means
fifteen Python processes, each with its own Mongo connection pool. That has
taken a host down before.

```bash
sudo sed -i 's/^WEB_CONCURRENCY=.*/WEB_CONCURRENCY=2/' /srv/tinymrp/instances/company1/.env
grep -q '^WEB_CONCURRENCY=' /srv/tinymrp/instances/company1/.env || \
  echo 'WEB_CONCURRENCY=2' | sudo tee -a /srv/tinymrp/instances/company1/.env
sudo ./deploy/scripts/update-instance.sh company1
```

---

## What is written where

| Path | Contents |
| --- | --- |
| `/srv/tinymrp/host/.env` | Host config: ACME email, base domain, proxy network |
| `/srv/tinymrp/caddy/Caddyfile` | Root Caddy config, importing the routes |
| `/srv/tinymrp/caddy/routes/*.caddy` | One route per instance |
| `/srv/tinymrp/instances/<name>/.env` | Instance config and secrets (root only) |
| `/srv/tinymrp/instances/<name>/compose.yml` | Rendered per-instance stack |
| `/srv/tinymrp/instances/<name>/deliverables/` | Deliverables, owned by `1000:1000` |
| `/srv/tinymrp/instances/<name>/mongo/` | Database files, owned by `999:999` |
| `/srv/tinymrp/backups/<name>/<stamp>/` | Backups |

Key entries in an instance `.env`:

| Key | Purpose |
| --- | --- |
| `INSTANCE_DOMAIN`, `INSTANCE_URL`, `TLS_MODE` | Identity and transport |
| `TINYMRP_URL` | The address the app uses to derive its cookie and CSP posture |
| `TINYMRP_TRUSTED_PROXY_HOPS=1` | Caddy is the one trusted proxy |
| `TINYMRP_ALLOWED_ORIGINS` | CORS allowlist, the instance's own origin |
| `MONGO_URI`, `MONGO_APP_USER`, `MONGO_APP_PASSWORD`, `MONGO_ROOT_*` | Database; the app connects as the scoped user, never root |
| `SECRET_KEY`, `SECURITY_PASSWORD_SALT` | Signing secrets |
| `RATE_LIMIT_STORAGE_URI=redis://redis:6379/0` | Shared counters |
| `WEB_CONCURRENCY` | Per-instance worker cap |

Back up `/srv/tinymrp/instances/*/.env` separately. Without it a database
backup cannot be restored into a usable instance.

---

## Operations

```bash
# code
sudo ./deploy/scripts/update-repo.sh                     # fetch and verify the repo
sudo ./deploy/scripts/update-instance.sh company1        # rebuild one, verify, roll back on failure
sudo ./deploy/scripts/update-all-instances.sh            # all of them, sequentially
sudo ./deploy/scripts/rollback-instance.sh company1      # manual rollback

# data
sudo ./deploy/scripts/backup-instance.sh company1
sudo ./deploy/scripts/backup-instance.sh company1 --no-deliverables
sudo ./deploy/scripts/backup-all.sh
sudo ./deploy/scripts/restore-instance.sh company1 /srv/tinymrp/backups/company1/<stamp>
sudo ./deploy/scripts/install-backup-job.sh              # nightly cron

# health and repair
sudo ./deploy/scripts/doctor.sh
sudo ./deploy/scripts/fix-deliverables-permissions.sh company1
sudo ./deploy/scripts/refresh-caddy-routes.sh
sudo ./deploy/scripts/enable-mongo-auth.sh company1      # instances created before auth was default
```

`backup-instance.sh` retention has three independent limits — `--keep-days`
(14), `--keep-count` (8) and `--max-total-gb` (10). Any can prune, and the
newest backup is never pruned.

`update-instance.sh` verifies the new container's health through the live Caddy
route and restores the previous image automatically if it does not come up.

Per-instance shell access:

```bash
docker logs -f tinymrp-company1-app
docker exec -it tinymrp-company1-app flask --app run.py user list
docker exec -it tinymrp-company1-app flask --app run.py demo install
```

---

## Capacity

| Instances | RAM | vCPU | Notes |
| --- | --- | --- | --- |
| 1 | 4 GB | 2 | Defaults are fine |
| 2–3 | 8 GB | 4 | Set `WEB_CONCURRENCY=2` per instance |
| 4–6 | 16 GB | 8 | Set `WEB_CONCURRENCY=2`; watch Mongo memory |
| 7+ | — | — | Split across hosts |

Disk is dominated by deliverables. Budget your CAD export size plus about 30%
for thumbnails, plus backup retention (`--max-total-gb` per instance).

---

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Certificate never issues | Public DNS `A` record points here; 80 and 443 open; `docker logs tinymrp-caddy` |
| `Host reverse proxy is not configured` | Run `install-host.sh` first |
| Instance healthy, route 502 | `sudo ./deploy/scripts/refresh-caddy-routes.sh`, then `doctor.sh` |
| Uploads fail, thumbnails missing | `sudo ./deploy/scripts/fix-deliverables-permissions.sh <instance>` |
| Host slow or out of memory | Too many workers; set `WEB_CONCURRENCY` per instance |
| Local-domain instance loops at login | `TLS_MODE`/`INSTANCE_URL` disagree with how you browse. [Details](07-troubleshooting.md#i-log-in-and-land-back-on-the-login-page) |

The reference for this path is
[deploy/README.md](../../deploy/README.md); this page is the orientation to it.
