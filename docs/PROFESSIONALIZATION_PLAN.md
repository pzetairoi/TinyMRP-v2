# TinyMRP — Professionalization Plan

Audit date: 2026-07-05. This document is the roadmap to bring the repository to industry standards for
security-sensitive, professional environments. It is organized as incremental phases: each phase is small
enough to implement and test on its own, and each ends with explicit acceptance criteria before moving on.

## 1. Current state assessment

### Already strong (keep and build on)

- Application security foundation: dual security modes (`compat`/`strict`), argon2 password hashing,
  Flask-Security with generic responses, CSRF protection (WTF + origin/referer guard), CORS allowlist,
  security headers + CSP, HSTS on secure requests, bearer-token-only `/api` in strict mode, ProxyFix,
  upload size caps, SSRF host allowlist on the file proxy.
- Protected file delivery: tokenized URLs, nginx `auth_request` on `/Deliverables`, `X-Accel-Redirect` support.
- API tokens with expiry, revocation and last-used tracking; audit logging of sensitive actions; RLS scoping.
- Deployment assets for all three tiers already exist: Windows LAN guide (waitress + nginx + firewall
  scripts), standalone `deploy/nginx.server.conf` + `tinymrp.service`, and a mature scripted Caddy
  multi-instance system (per-instance Docker networks and databases, private Mongo, doctor/update/rollback
  scripts, per-instance Nextcloud).
- CI: ruff, black, mypy (partial), bandit, pytest, npm audit, frontend build, gitleaks. 145 passing tests.
- SECURITY.md with threat model and incident notes; MIGRATION.md strict-mode rollout checklist.

### Gap summary (what the phases below fix)

| # | Gap | Risk | Phase |
|---|-----|------|-------|
| G1 | No rate limiting or login throttling anywhere | Brute force, credential stuffing | 1 |
| G2 | File/extra-file tokens never expire (`URLSafeSerializer`, no TTL) | Leaked link = permanent access | 1 |
| G3 | CSP allows `unsafe-inline` scripts/styles | XSS depth reduced | 1 |
| G4 | No MFA/2FA option | Required in secured environments | 1 |
| G5 | `print()` used instead of structured logging | No forensics, no aggregation | 1 |
| G6 | `requirements.txt` mixes runtime with tooling (pipenv, pip-audit, build, etc.) | Bloated attack surface + image | 0 |
| G7 | No `.dockerignore`; Dockerfile copies repo before installing deps | Secrets/junk in image, slow builds | 2 |
| G8 | Mongo runs without authentication (network isolation only) | Single-layer defense | 2 |
| G9 | Compose seeds default admin `ChangeMe123!` by default | Default credentials | 2 |
| G10 | No image publishing, scanning (trivy), SBOM, or dependency updates automation | Supply chain blind spots | 0/2 |
| G11 | nginx templates have no TLS (443) server block, headers, or rate-limit zones | Manual TLS = inconsistent hardening | 3 |
| G12 | No data backup/restore tooling (Mongo, deliverables, Nextcloud) | Unrecoverable data loss | 4 |
| G13 | Nextcloud instances installed without hardening pass (headers, bruteforce config, backups) | Exposed collaboration surface | 5 |
| G14 | Ruff rule set is syntax-only; mypy covers 2 files; no coverage gate; no shellcheck on deploy scripts | Quality regressions slip through | 0/4 |
| G15 | Monolithic 27 KB README; no per-tier hardening guides or ops runbook | Operator error | 7 |
| G16 | No release process (tags, changelog, versioned images) | Untraceable deployments | 0 |
| G17 | `compat` mode is the default; strict-mode production posture is opt-in | Insecure-by-default installs | 3 |

## 2. Deployment tiers (target shapes)

- **T1 — Windows development / LAN**: native Python + MongoDB + waitress behind nginx for Windows,
  LAN-only, no internet exposure. Target: one-script bootstrap, parity with production behavior.
- **T2 — Standalone Linux server with nginx**: single host, manual or scripted install, systemd +
  gunicorn (or single-instance Docker), nginx with full TLS termination. Target: hardened single-tenant
  production.
- **T3 — Multi-instance Caddy hosts**: the scripted `deploy/scripts` path. Caddy with automatic HTTPS,
  N isolated instances per host, optional per-instance Nextcloud. Target: repeatable fleet operations
  with backups, monitoring, and tested rollback.

Phases 0–2 harden the application and images shared by every tier; phases 3–5 harden each tier; phases
6–7 finish developer experience, operations, and documentation.

---

## Phase 0 — Repository and supply-chain hygiene (quick wins)

**Goal:** trustworthy builds and a CI that catches real problems.

1. Split dependencies: `requirements.txt` (runtime only), `requirements-dev.txt` (test/lint), remove
   pipenv/pip-tools/build/cyclonedx/pip-audit from runtime. Regenerate with pinned versions.
2. Add `.dockerignore` (exclude `.git`, `.venv`, `tests`, `docs`, `solidworks-addin`, `instance`,
   `frontend/node_modules`, `*.log`, `.env*`).
3. CI additions: `pip-audit` job, CycloneDX SBOM artifact for backend and frontend, `shellcheck` on
   `deploy/scripts/**`, coverage report with an initial floor (e.g. 60%, ratchet up).
4. Enable Dependabot (or Renovate) for pip, npm, docker, and GitHub Actions ecosystems.
5. Add `pre-commit` config (ruff, black, gitleaks, end-of-file/trailing whitespace).
6. Introduce versioning: `VERSION` file or git tags + `CHANGELOG.md` (Keep a Changelog format);
   surface the running version in the UI footer/health endpoint.
7. Widen ruff rules gradually (`E`, `F`, `W`, `B`, `S` bandit-lite) with a per-rule ignore list to burn down.

**Acceptance:** CI green with new jobs; image builds without dev tooling; `pip-audit`/`npm audit` clean or
with documented waivers; a tagged release exists.

## Phase 1 — Application security hardening

**Goal:** close the app-level gaps that matter in hostile networks.

1. **Rate limiting (G1):** add Flask-Limiter with in-memory default and Redis option for T3. Limits on
   `/login`, password endpoints, token verification, and a global API budget. Optional account lockout
   with exponential backoff (audit-logged).
2. **Expiring file tokens (G2):** switch `files_access.py` and `extra_files.py` to `URLSafeTimedSerializer`
   with configurable TTL (default e.g. 24 h; `FILES_TOKEN_TTL_SECONDS`). Honor the existing
   `FILES_ALLOW_LEGACY_TOKENS` flag for a migration grace period, then default it off.
3. **MFA (G4):** enable Flask-Security TOTP two-factor as an opt-in per user, with an org-level
   `SECURITY_TWO_FACTOR_REQUIRED` switch for strict deployments.
4. **Structured logging (G5):** replace `print()` with the `logging` module app-wide; JSON log formatter
   option (`LOG_FORMAT=json`), request-ID middleware, and login/denied-access events at WARNING.
5. **CSP tightening (G3):** move inline scripts/styles in Jinja templates to static files or nonces;
   drop `unsafe-inline` in strict mode first, then everywhere. Replace obsolete `X-XSS-Protection`;
   upgrade `Referrer-Policy` to `strict-origin-when-cross-origin`.
6. Session review: absolute session lifetime, remember-cookie duration, logout-everywhere on password
   change (Flask-Security uniquifier rotation — verify it triggers).

**Acceptance:** new unit tests for limiter, token TTL, and MFA flows; full suite green; bandit clean;
manual checklist: brute-force attempt throttled, expired file link rejected, CSP has no `unsafe-inline`
in strict mode.

## Phase 2 — Container and compose hardening

**Goal:** production-grade images and compose definitions shared by T2/T3.

1. Dockerfile: copy `requirements.txt` first for layer caching; install runtime deps only; pin base
   images by digest; `HEALTHCHECK` against `/api/health`; verify the non-root user owns only what it
   needs; add `gunicorn` timeouts and `--max-requests`/jitter.
2. Compose: enable Mongo authentication (`MONGO_INITDB_ROOT_*` + app user with least privilege),
   `depends_on: condition: service_healthy`, `read_only: true` + `tmpfs` for the app container,
   `cap_drop: [ALL]`, `security_opt: no-new-privileges`, remove default admin credentials — require
   explicit `TINYMRP_ADMIN_*` or fail seeding with a clear message (G9).
3. Publish images: GitHub Actions workflow building multi-stage image on tag, pushing to GHCR with
   trivy scan gate + SBOM attached; hadolint in CI.
4. Make `create-instance.sh` optionally consume the published image instead of building from source
   on every host (faster, reproducible fleet updates).

**Acceptance:** `docker compose up` smoke test in CI (health endpoint 200); trivy no HIGH/CRITICAL
unwaived; container runs read-only as non-root; fresh install refuses to seed a default admin.

## Phase 3 — Tier T2: standalone Linux + nginx (manual and scripted)

**Goal:** a hardened, documented single-server path.

1. Expand `deploy/nginx.server.conf` into a complete TLS template: 443 server block, modern TLS
   (TLS 1.2/1.3, strong ciphers), OCSP stapling, HTTP→HTTPS redirect, HSTS, security headers at the
   proxy, `limit_req` zones for `/login` and `/api`, `client_max_body_size` aligned with upload caps,
   gzip for static assets. Provide certbot and internal-CA variants.
2. Harden `deploy/tinymrp.service`: `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`,
   `PrivateTmp`, `ReadWritePaths` only for deliverables/instance, `Restart=on-failure`, dedicated
   `tinymrp` system user.
3. New `deploy/scripts/install-server.sh` (scripted variant of the manual guide): idempotent, installs
   python/mongo/nginx, creates user + venv, writes env from prompts, enables UFW (80/443/SSH only),
   installs the systemd unit, runs a post-install self-check. Manual guide remains as the documented
   equivalent.
4. fail2ban jail template for nginx auth failures + app login failures (uses the structured logs from
   Phase 1); logrotate config for app logs.
5. Default posture: installer sets `TINYMRP_SECURITY_MODE=strict` and generates strong secrets (G17).

**Acceptance:** clean Ubuntu VM → running hardened instance via script in one pass; `testssl.sh` grade A;
doctor-style self-check passes; fail2ban bans a simulated brute force; reboot survives.

## Phase 4 — Tier T3: Caddy multi-instance fleet operations

**Goal:** the scripted fleet becomes fully operable: backups, monitoring, tested recovery.

1. **Backups (G12):** new `backup-instance.sh` / `backup-all.sh`: `mongodump` per instance DB +
   deliverables snapshot (restic or rsync hard-link rotation), retention policy, optional off-host
   target (S3/SFTP), and `restore-instance.sh` with a verification mode (restore into a scratch
   instance and run health checks). Cron/systemd-timer installer.
2. Caddy route hardening: shared snippet with security headers (HSTS preload-ready, X-Content-Type-Options,
   Referrer-Policy, frame-ancestors), per-instance rate limiting (caddy-ratelimit) and body limits.
3. Script quality: shellcheck-clean (from Phase 0 CI), `--dry-run` mode for destructive scripts,
   bats-core tests for the pure-bash helpers in `lib/`.
4. Update strategy: `update-all-instances.sh` gains canary ordering (update one, health-check, continue),
   and every update snapshots the instance (config + DB dump) first; document the maintenance-window flow.
5. Host monitoring: expose `/api/health` per instance through doctor; optional node-exporter +
   Prometheus scrape config; disk-space and cert-expiry checks in `doctor.sh`.

**Acceptance:** disaster drill on a test host — destroy an instance, restore from backup, data intact;
canary update rolls back automatically on failed health check; shellcheck/bats green in CI.

## Phase 5 — Nextcloud protection

**Goal:** the per-instance Nextcloud is as hardened as the app itself.

1. Caddy headers for NC domains per Nextcloud admin manual (HSTS ≥ 15552000, no-sniff, frame policy,
   well-known redirects for caldav/carddav).
2. Post-install hardening in `install-nextcloud-instance.sh` via `occ`: confirm bruteforce protection
   enabled, set `overwriteprotocol https`, correct `trusted_domains`/`trusted_proxies`, disable public
   registration, set default phone region, background jobs via cron, `maintenance_window_start`.
3. fail2ban jail for Nextcloud auth log; optional server-side encryption decision documented (trade-offs).
4. Include NC data + DB in the Phase 4 backup system; test restore.
5. Update policy: pin NC major version in compose, scripted minor updates with pre-update snapshot;
   scan job (`scan-nextcloud-instance.sh`) runs least-privileged.
6. Network posture check in doctor: NC containers reachable only via Caddy; no published DB ports.

**Acceptance:** scan.nextcloud.com (or `occ security:*` equivalents) reports A/A+; restore drill passes;
doctor validates headers and network isolation.

## Phase 6 — Tier T1: Windows development experience

**Goal:** a new developer or LAN pilot is productive in minutes, with prod-parity behavior.

1. `deploy/windows/setup-dev.ps1`: checks prerequisites, creates venv, installs deps, writes `.env.dev`
   from the example with generated secrets, seeds an admin (prompted, never default), starts Mongo check,
   launches the app; `npm install`/Vite dev-server steps for frontend work.
2. Keep the existing LAN service scripts (waitress + nginx + firewall) and align them with Phase 3
   headers/limits where nginx-for-Windows supports them; document the delta from production.
3. Make dev defaults safe: dev script runs `compat` locally but prints a banner listing every
   production-only control that is off.

**Acceptance:** clean Windows VM → running dev instance with one script in <15 min; documented smoke
checklist (login, upload pack, part detail, PDF binder) passes.

## Phase 7 — Observability, documentation, and release round-up

**Goal:** the "professional finish": operators can run, monitor, upgrade, and audit the system from docs alone.

1. Metrics: optional Prometheus endpoint (request rates, latency, queue depths, thumbnail/docpack timings);
   alerting starter rules (disk, cert expiry, error rate, backup age).
2. Documentation restructure under `docs/`:
   - `install/` — one guide per tier (T1/T2/T3) + Nextcloud.
   - `security/` — hardening guide per tier, threat model (expand SECURITY.md), secrets rotation runbook.
   - `operations/` — backup/restore, upgrade, incident response, audit-log review, monitoring.
   - `api/` — token auth + endpoint reference (consider OpenAPI generation).
   - Slim README pointing to the above.
3. Release process: signed tags, release notes from CHANGELOG, versioned images, upgrade notes per release;
   support matrix (Python/Mongo/Node versions).
4. External validation: run OWASP ZAP baseline scan against a staging instance in CI (non-blocking at
   first); schedule a manual pen-test checklist pass; fix or waive findings.
5. Optional compliance mapping: short matrix of controls → OWASP ASVS L2 / CIS Docker benchmarks for
   customers who ask.

**Acceptance:** a third party can install T2 or T3 from docs alone; ZAP baseline has no unwaived alerts;
release v1.0.0 published with signed artifacts.

---

## 3. Suggested order and effort

| Phase | Depends on | Rough effort | Value |
|-------|-----------|--------------|-------|
| 0 Hygiene | — | 1–2 days | High (unblocks everything) |
| 1 App security | 0 | 3–5 days | Critical (G1–G5) |
| 2 Containers | 0 | 2–3 days | High |
| 3 T2 nginx | 1, 2 | 2–4 days | High |
| 4 T3 fleet ops | 2 | 4–6 days | Critical for production fleets (backups!) |
| 5 Nextcloud | 4 | 2–3 days | High where NC is used |
| 6 Windows dev | 1 | 1–2 days | Medium |
| 7 Round-up | all | 3–5 days | High (professional finish) |

Fastest risk reduction if time is short: Phase 0 → Phase 1 items 1–2 (rate limiting + token TTL) →
Phase 2 item 2 (Mongo auth + no default admin) → Phase 4 item 1 (backups).

## 4. Working agreement per phase

For every phase: implement on a branch, keep the full test suite green, add tests for new behavior,
update the relevant docs in the same PR, and finish with the phase's acceptance checklist executed on a
disposable VM (T2/T3 phases) before merging. Each phase ends with a tagged pre-release so environments
can adopt incrementally.
