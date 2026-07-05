# Updating production instances safely (Phase 0/1/2 changes and onward)

## Phase 2 rollout notes (container hardening)

Applied on the next rebuild via the same canary procedure. What changes:

| Change | Operator impact |
|--------|-----------------|
| Instance compose template hardened (`read_only` rootfs, `tmpfs /tmp`, `cap_drop: ALL`, `no-new-privileges`, health-gated startup, healthcheck moved to `/api/health`) | `update-instance.sh` regenerates the compose file and recreates containers as usual. If any custom workflow writes inside the container filesystem (outside `/data/deliverables` and `/tmp`), it will now fail — report it and temporarily remove `read_only: true` from that instance's compose while we fix the write path. |
| Dockerfile rebuilt for caching + smaller surface (no compiler toolchain, gunicorn timeouts and worker recycling, container HEALTHCHECK) | First rebuild takes the usual time; later rebuilds are much faster. |
| No default admin credentials; entrypoint refuses `ChangeMe123!` | Existing instances have users, so seeding is skipped entirely — no impact. Fresh instances print a generated one-time admin password in `docker logs <app>` when `TINYMRP_ADMIN_PASSWORD` is unset. |
| Release images published to GHCR on version tags (trivy-gated) | Optional: deploy pre-built images with `update-instance.sh <name> --image ghcr.io/<owner>/tinymrp-app:vX.Y.Z` instead of building on-host. |
| Mongo authentication available (opt-in) in the single-host compose | Nothing changes unless you set `MONGO_ROOT_USER`/`MONGO_ROOT_PASSWORD`. Fleet instances keep their per-instance internal-network isolation; scripted per-instance Mongo auth arrives with the Phase 4 fleet work. |

### Enabling Mongo auth on an EXISTING single-host compose deployment

Auth must be configured before Mongo enforces it — do this in one maintenance window:

```bash
# 1) Create the root user while auth is still off
docker compose exec mongo mongosh --eval '
  db.getSiblingDB("admin").createUser({
    user: "root", pwd: "<STRONG-PASSWORD>", roles: [ { role: "root", db: "admin" } ]
  })'

# 2) Add to .env:
#    MONGO_ROOT_USER=root
#    MONGO_ROOT_PASSWORD=<STRONG-PASSWORD>
#    MONGO_URI=mongodb://root:<STRONG-PASSWORD>@mongo:27017/tinymrp-v2?authSource=admin

# 3) Recreate with auth enforced
docker compose up -d --force-recreate mongo app
curl -fsS http://localhost:${HTTP_PORT:-5000}/api/health
```

To roll back: remove the three `.env` entries and `docker compose up -d --force-recreate`.


## Phase 1 rollout notes (application security hardening)

Phase 1 activates at the NEXT rebuild of each instance. Same canary procedure as below, plus:

| Change | Operator impact |
|--------|-----------------|
| Rate limiting ON by default (login 10/min per client IP) | Shared-NAT offices doing bulk logins may hit it; raise via `RATE_LIMIT_LOGIN` or disable with `RATE_LIMIT_ENABLED=false`. Running >1 gunicorn worker? Budgets are per-worker with memory storage — set `RATE_LIMIT_STORAGE_URI=redis://...` for exact shared limits (approximate limits without it are fine for most). |
| File links now expire after 24 h | Normal UI use unaffected (fresh tokens per page load). Users who bookmarked raw `/files/<token>` links must re-open from the UI. Migration window: set `FILES_ALLOW_LEGACY_TOKENS=true` for a week or two, then remove it. |
| TOTP 2FA available | OFF by default — nothing changes until you set `SECURITY_TWO_FACTOR_ENABLED=true` + `SECURITY_TOTP_SECRETS` per instance. |
| Structured logs + X-Request-ID | Additive. Set `LOG_FORMAT=json` per instance when you want machine-readable logs. |
| Referrer-Policy / X-XSS-Protection header changes | No functional impact on the app. |
| New Python deps (Flask-Limiter, limits, cryptography) | Installed automatically on image rebuild / `pip install -r requirements.txt`. |

Post-update spot checks per instance: log in normally (should NOT be throttled), fail login
11× rapidly from one machine (should get "Too many attempts"), open a part file from the UI
(fresh token works), check response headers contain `X-Request-ID`.


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
