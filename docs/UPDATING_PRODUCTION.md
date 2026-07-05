# Updating production instances safely (Phase 0 changes and onward)

This guide gives the exact commands to keep existing Caddy multi-instance hosts alive when pulling
new versions of this repository, and what changed in Phase 0 that operators should know.

## What Phase 0 changed — impact on running instances

**Nothing changes for running containers until you rebuild them.** Phase 0 touched dependency
manifests, CI, build context, and three latent code bugs. When you DO rebuild:

| Change | Impact on rebuild |
|--------|-------------------|
| `requirements.txt` split (runtime only, same pinned versions) | Same library versions as today, plus `psutil`/`waitress`/`requests` now correctly declared. Validated: full test suite passes on a clean install. |
| `.dockerignore` added | Smaller, faster builds. Verified to keep everything the image serves (`/downloads/addin`, `/downloads/macro`, help docs, frontend build inputs). |
| `VERSION` file + `/api/health` now returns `server_version: 2.0.0` | Additive only. Update health probes only if they assert exact JSON. |
| Bug fixes (`current_app` import in docpacks view, `stringWidth` import order, `datetime` annotation import) | Strictly fixes; one 500-instead-of-400 path and one label-width glitch go away. |
| Earlier cleanup: `OLD/` folder removed, macro relocated | `/downloads/macro` now serves `app/static/misc/TinyMRP.swp` (the newest macro, Sep 2025). If a host's checkout still has `OLD/`, it is simply ignored. |
| `docker/app/entrypoint.sh` `$*` fix | Cosmetic logging fix only. |

Dev-tooling packages that used to ride along in production images (pipenv, pip-audit, pip-tools,
build, rich, etc.) are no longer installed. They were never imported by the app.

## Recommended update procedure (per host)

Run everything as root (sudo) from the repo checkout used by the host.

```bash
# 0) Snapshot state BEFORE updating (manual until Phase 4 backup scripts land)
#    For each instance you care about:
docker exec $(docker ps --format '{{.Names}}' | grep '<instance>.*mongo') \
  mongodump --archive --gzip > /srv/backups/<instance>-mongo-$(date +%Y%m%d-%H%M).archive.gz

# 1) Pull the new code (also re-fixes script exec bits)
sudo ./deploy/scripts/update-repo.sh --ref main --alias latest

# 2) Canary: update ONE low-risk instance first
sudo ./deploy/scripts/update-instance.sh <canary_instance> --health-timeout 300

# 3) Verify the canary
sudo ./deploy/scripts/doctor.sh --instance <canary_instance>
curl -fsS https://<canary-domain>/api/health
#    Expect: {"ok": true, ..., "server_version": "2.0.0", ...}
#    Then log in and spot-check: parts list, part detail, a PDF binder, a file download.

# 4) Roll out to the rest
sudo ./deploy/scripts/update-all-instances.sh --health-timeout 300

# 5) Full host check
sudo ./deploy/scripts/doctor.sh --all
```

## If something goes wrong

```bash
# Roll a single instance back to its previous image/config snapshot:
sudo ./deploy/scripts/rollback-instance.sh <instance_name>

# If data must be restored too (from the step-0 dump):
sudo ./deploy/scripts/rollback-instance.sh <instance_name> \
  --restore-mongo-from /srv/backups/<instance>-mongo-<stamp>.archive.gz
```

`update-instance.sh` records the previous image and configuration before switching, which is what
`rollback-instance.sh` restores. The step-0 mongodump is your belt-and-braces data restore point.

## Keeping instances alive WITHOUT updating

Nothing in this repository affects running containers until `update-instance.sh` (or a manual
`docker compose up --build`) is executed for that instance. To hold a host at its current version,
simply do not run the update scripts; `doctor.sh` remains safe to run at any time.

## Standalone (non-Docker) nginx servers — T2

```bash
cd /opt/tinymrp            # or wherever the checkout lives
sudo -u tinymrp git pull
sudo -u tinymrp ./.venv/bin/pip install -r requirements.txt   # same pins + newly declared deps
sudo systemctl restart tinymrp
curl -fsS http://127.0.0.1:8000/api/health
```

## Windows dev/LAN machines — T1

```powershell
git pull
.\.venv\Scripts\pip install -r requirements.txt          # runtime deps (now includes waitress)
.\.venv\Scripts\pip install -r requirements-dev.txt      # only if you run tests/lint locally
Restart-Service TinyMRP                                   # if installed as a service
```
