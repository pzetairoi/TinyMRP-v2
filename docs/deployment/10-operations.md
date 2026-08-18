# 10 — Backups, updates and uninstall

The routine operations, per deployment path.

> **Host requirements for the shell tooling.** `tinymrp.sh` and the
> `deploy/scripts/*` helpers assume **GNU coreutils and findutils**, which is
> what Ubuntu and Debian ship: `find -printf`, `stat -c`, `du -b`,
> `sha256sum`, `sed -i`. On a BusyBox userland (Alpine) backup retention
> pruning silently does nothing. Run the Linux tooling on Ubuntu/Debian, or
> use the container path, which carries its own userland.

- [What a complete backup contains](#what-a-complete-backup-contains)
- [Container stack](#container-stack-deploycommunity)
- [VPS multi-instance](#vps-multi-instance)
- [Linux bare metal](#linux-bare-metal)
- [Windows service](#windows-service)
- [Restore drills](#restore-drills)
- [Monitoring](#monitoring)
- [Moving an instance to another host](#moving-an-instance-to-another-host)

---

## What a complete backup contains

Three parts. A backup missing any of them cannot produce a working instance.

| Part | Contents | Why it is not optional |
| --- | --- | --- |
| **Database** | Parts, BOMs, users, roles, jobs, orders, audit log | The application state |
| **Configuration** | `SECRET_KEY`, `SECURITY_PASSWORD_SALT`, Mongo credentials | A different `SECRET_KEY` signs everyone out and kills every issued file link; a different `SECURITY_PASSWORD_SALT` invalidates **every password** |
| **Deliverables** | The CAD file tree | The database stores paths and hashes, not bytes |

The deliverables are usually far the largest, and often already covered by
another backup (a NAS snapshot, the CAD vault). The database is typically a few
MB compressed, so back it up far more frequently than the files.

---

## Container stack (`deploy/community`)

### Backup

```bash
cd deploy/community
./tinymrp.sh backup                        # database + configuration
./tinymrp.sh backup --include-deliverables # add the file tree
```

Written to `deploy/community/backups/<UTC-stamp>/`:

| File | Contents |
| --- | --- |
| `mongo.archive.gz` | `mongodump` archive, gzip-verified and size-checked |
| `config.env` | Copy of `.env`, including the secrets |
| `deliverables.tar.gz` | Present only with `--include-deliverables` |
| `metadata.txt` | Timestamp, image tag, uncompressed byte count |
| `checksums.sha256` | Over all of the above |

`backup` refuses to write an archive whose uncompressed content is under 1 KB,
so an empty dump cannot masquerade as a good backup.

Retention, from `.env`, any of which can prune (the newest is never pruned):

```bash
BACKUP_KEEP_DAYS="14"
BACKUP_KEEP_COUNT="8"
BACKUP_MAX_TOTAL_GB="10"
```

Schedule it:

```bash
crontab -e
# 0 2 * * * cd /opt/tinymrp_v2/deploy/community && ./tinymrp.sh backup >> /var/log/tinymrp-backup.log 2>&1
# 0 3 * * 0 cd /opt/tinymrp_v2/deploy/community && ./tinymrp.sh backup --include-deliverables >> /var/log/tinymrp-backup.log 2>&1
```

Copy the backups off the host. A backup on the same disk as the database
protects against mistakes, not against losing the machine.

### Restore

```bash
./tinymrp.sh restore backups/2026-08-14T02-00-00Z
./tinymrp.sh restore backups/2026-08-14T02-00-00Z --include-deliverables --yes
```

Verifies the checksums and the archive, stops the app, **drops collections
created after the backup**, replays the dump, restarts, and waits for health.
Without `--yes` it asks you to type `RESTORE`.

Two deliberate asymmetries:

- The database restore is **exact**: collections created after the backup are
  removed, so what you get is the state at backup time and nothing else.
- The deliverables restore is **preservation-first**: the snapshot is overlaid
  and newer files are not deleted, because a file added since the backup is
  usually work you want to keep.
- `config.env` is kept as recovery evidence and is **not** applied over live
  credentials. Copy values across by hand if you need them.

### Update

There are two kinds of Community install and each has its own update command.
You do not have to remember which you have — running the wrong one prints the
right one.

| How it was installed | Update with |
| --- | --- |
| From a git checkout, `install.sh --build` | `./tinymrp.sh update` *(no argument)* |
| From a versioned release bundle | `./tinymrp.sh update v2.1.0` |

#### From a git checkout — `./tinymrp.sh update`

This is the common case for anyone who cloned the repository.

```bash
cd /opt/tinymrp_v2/deploy/community
./tinymrp.sh update
```

It does the whole sequence for you:

1. checks the checkout is clean, on a branch, and has an upstream;
2. `git fetch` and **fast-forward only** — it refuses to merge, so a diverged
   host is reported rather than silently resolved;
3. works out the new tag, `<VERSION>-src.<short-sha>`, and stops early with
   "already up to date" if that image is already built and running;
4. takes a verified Mongo backup **before** touching anything;
5. rebuilds the image from `docker/app/Dockerfile`;
6. rewrites `TINYMRP_VERSION` and recreates only the app container;
7. waits for health, and on failure puts the previous version back and tells
   you which backup to fall back on.

The previous image is kept, so that rollback needs no rebuild. Mongo, Redis and
your deliverables are never touched. Expect a few minutes; Docker's layer cache
makes later updates much faster than the first build.

It refuses to run with uncommitted changes in the checkout. That is deliberate:
a rebuild bakes the working tree into the image, so building with local edits
present produces something nobody can reproduce later. Commit or stash them
first.

If the update fails, nothing is lost — the running instance is left on the old
version. `./tinymrp.sh status` shows what is running and `./tinymrp.sh logs`
shows why.

#### From a release bundle — `./tinymrp.sh update v2.1.0`

```bash
./tinymrp.sh update v2.1.0
```

Takes a verified backup, rewrites `TINYMRP_VERSION`, pulls, recreates the app
container and waits for health. If the new container does not become healthy it
restores the previous image reference automatically and tells you which backup
to fall back on. Only the app image changes; data is untouched.

`latest` is rejected: an unpinned tag makes "which version is running" and
"roll back to the previous one" unanswerable.

Asking a checkout-built install for a version number is also rejected, with an
explanation: its image was built locally and never published, so there is no
such tag to pull.

#### Rolling back

The previous image is still on the host, so a rollback is a version swap:

```bash
cd deploy/community
docker images tinymrp-local            # find the previous tag
./tinymrp.sh backup                    # capture the current state first
sed -i 's/^TINYMRP_VERSION=.*/TINYMRP_VERSION="2.0.0-src.abc1234"/' .env
docker compose --env-file .env -f compose.yaml up -d --no-deps --force-recreate --wait app
```

If the update itself failed, this already happened automatically.

### Uninstall

```bash
./tinymrp.sh uninstall                       # containers only; all data preserved
./tinymrp.sh uninstall --delete-data --yes   # also delete the Docker volumes
```

Neither ever deletes your deliverables folder or your backups. After a plain
`uninstall`, `./tinymrp.sh start` brings everything back with its data intact.

---

## VPS multi-instance

```bash
sudo ./deploy/scripts/backup-instance.sh company1
sudo ./deploy/scripts/backup-instance.sh company1 --no-deliverables
sudo ./deploy/scripts/backup-instance.sh company1 --raw          # brief downtime
sudo ./deploy/scripts/backup-all.sh
sudo ./deploy/scripts/install-backup-job.sh                      # nightly cron

sudo ./deploy/scripts/restore-instance.sh company1 /srv/tinymrp/backups/company1/<stamp>

sudo ./deploy/scripts/update-repo.sh
sudo ./deploy/scripts/update-instance.sh company1
sudo ./deploy/scripts/update-all-instances.sh
sudo ./deploy/scripts/rollback-instance.sh company1
```

Backups land in `/srv/tinymrp/backups/<instance>/<UTC-stamp>/` with
`mongo.archive.gz`, `deliverables.tar.gz`, `config/` and `manifest.env`.
Retention: `--keep-days 14`, `--keep-count 8`, `--max-total-gb 10`.

`--no-deliverables` is the cheap one — the database is a couple of MB
compressed while the file tree can be many GB — so a sensible schedule is
nightly database-only and weekly full.

`update-instance.sh` verifies health **through the live Caddy route**, not just
the container, and rolls the image back automatically on failure.

---

## Linux bare metal

There is no bundled tool; the script in
[02 — Linux bare metal → Backups](02-linux-bare-metal.md#backups) captures all
three parts. Update by re-running the installer after `git checkout`; it syncs
code and keeps your `/etc/tinymrp/.env` and certificates.

Uninstall:

```bash
sudo systemctl disable --now tinymrp
sudo rm /etc/systemd/system/tinymrp.service && sudo systemctl daemon-reload
sudo rm -f /etc/nginx/sites-enabled/tinymrp /etc/nginx/sites-available/tinymrp
sudo systemctl reload nginx
sudo rm -rf /opt/tinymrp_v2 /opt/tinymrp_venv
# keep these unless you are certain:
# sudo rm -rf /etc/tinymrp /srv/tinymrp/deliverables
# sudo apt-get purge mongodb-org
```

---

## Windows service

See [03 — Windows LAN → Backups](03-windows-lan.md#backups) for the scheduled
task, and [Updating](03-windows-lan.md#updating) for the upgrade sequence.

Uninstall:

```powershell
Stop-Service TinyMRP-App
sc.exe delete TinyMRP-App
Stop-Service TinyMRP-Nginx -ErrorAction SilentlyContinue
nssm remove TinyMRP-Nginx confirm
Get-NetFirewallRule -Group "TinyMRP LAN" | Remove-NetFirewallRule
Remove-Item -Recurse -Force C:\TinyMRP\app
# keep C:\TinyMRP\config and C:\TinyMRP\data unless you are certain
```

---

## Restore drills

A backup you have never restored is a hypothesis. Test it quarterly, on a
disposable host:

1. Install a fresh instance on scratch hardware or a throwaway VM.
2. Copy the newest backup across.
3. Restore it.
4. Sign in with a **production** account — this is what proves the salt and
   signing key came across intact.
5. Open a part, its BOM, and download one file — this proves the deliverables
   and the database agree.
6. Record the wall-clock time. That number is your real recovery time
   objective.
7. Destroy the test host.

Step 4 is the one that catches a configuration backup that was never taken.

---

## Monitoring

Two unauthenticated endpoints:

| Endpoint | Meaning | Use for |
| --- | --- | --- |
| `/api/health` | The process is alive | Liveness |
| `/api/ready` | Mongo reachable **and** the deliverables volume has at least `READINESS_MIN_FREE_DISK_MB` free | Readiness, load-balancer membership |

Use `/api/ready` for alerting. `/api/health` returns ok whenever the process is
running, including when the database is unreachable or the volume is unmounted.

```bash
*/5 * * * * curl -fsS http://localhost:5000/api/ready >/dev/null || \
  echo "TinyMRP not ready on $(hostname)" | mail -s "TinyMRP alert" ops@yourcompany.com
```

Worth watching:

- disk free on the deliverables volume (readiness fails below 512 MB by default,
  and a full disk corrupts imports mid-write);
- container or service restarts;
- `SECURITY:` lines in the log — unauthenticated Mongo, or a plain-HTTP
  transport you did not intend;
- backup age and size — a backup that suddenly shrinks is the interesting one;
- certificate expiry, if you are not using Caddy's automatic renewal.

For log aggregation set `LOG_FORMAT=json`; every line becomes one JSON object
carrying the request id.

---

## Moving an instance to another host

1. On the old host, take a full backup including deliverables, and copy the
   configuration file separately.
2. Install TinyMRP on the new host at the **same version**.
3. Stop the new instance.
4. Restore the database and the deliverables.
5. Copy `SECRET_KEY`, `SECURITY_PASSWORD_SALT` and the Mongo credentials from
   the old configuration into the new one. Without this, everyone is signed
   out and no password works.
6. Update `TINYMRP_URL` (and `TINYMRP_ALLOWED_ORIGINS`) if the address changed
   — including the scheme.
7. Start, then run the
   [five-minute acceptance test](06-first-run.md#a-five-minute-acceptance-test).
8. Repoint DNS or the hosts entries, and update the SolidWorks add-in backend
   URL on each workstation if the address changed.

Upgrading and moving at the same time turns two straightforward operations into
one hard one. Move first, verify, then upgrade.
