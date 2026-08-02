# Changelog

All notable changes to TinyMRP are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Security (Phase 1B — API-token lifecycle)
- New API tokens expire after 90 days by default and cannot exceed the
  operator-configured 365-day maximum. Invalid lifetime configuration fails
  closed; existing no-expiry tokens remain visible as legacy so deployed
  SolidWorks clients can be rotated deliberately instead of breaking silently.
- Token authentication now rejects inactive or deleted owners on every request.
  Account deactivation and self-service, administrator, CLI or disposable-test
  password resets revoke the user's API tokens; reactivation does not restore them.
- Users can rotate or explicitly revoke tokens and see created, expiry, last-used
  and lifecycle status. Security administrators can revoke one token or perform a
  global API-token logout, but cannot mint or retrieve another user's secret.
- Token secrets remain hash-only at rest and are returned once. Lifecycle actions
  are audit logged with bearer actors attributed correctly. Session invalidation
  remains the separate Phase 1C control.

### Fixed
- Container initialization now uses canonical standard roles, creates a fresh
  `administrator` only from explicit operator credentials, never logs generated
  passwords, preserves existing users on restart/update, and prevents application
  launch after unrecoverable bootstrap failure. Fresh-Compose and guided VPS/Caddy
  regression gates cover the supported deployment paths.
- The standalone Linux and Windows one-folder installers now bootstrap safely
  without resetting an existing administrator or displaying an unusable replacement
  password during upgrades.
- Uploads failed with "Permission denied: /data/deliverables/png" on instances built
  from the Phase-2 image: `useradd --system` assigned appuser a UID below 1000 while
  the deploy scripts chown the deliverables mount to 1000:1000. The image now pins
  appuser to UID/GID 1000; `create-instance.sh` pre-creates the full artifact folder
  set (3mf, bom, datasheet, dxf, edr, extra, pdf, pic, ply, png, reports, step, stl,
  temp, thumbs); the entrypoint self-heals missing folders and reports a non-writable
  deliverables root at startup; `doctor.sh` checks in-container writability.

### Operations (Phase 4 — Caddy fleet, tier T3)
- Backup system: `backup-instance.sh` (online mongodump + deliverables + config snapshot,
  retention pruning, optional raw Mongo snapshot compatible with
  `rollback-instance.sh --restore-mongo-from`, `--dry-run`), `backup-all.sh`, and
  `install-backup-job.sh` (systemd timer, nightly + jitter, idle IO priority).
- `restore-instance.sh` with a safe default `--verify` mode (restores the dump into a
  throwaway network-less container and reports collection/document counts), plus
  `--database` (auto-saves a pre-restore dump) and `--deliverables` restores with
  post-restore health checks.
- `update-all-instances.sh` gained `--canary <instance>` (canary first, abort rollout on
  canary failure) and `--backup-first` (DB + config dump immediately before each update).
- Caddy routes now emit security headers (HSTS for TLS modes, nosniff, referrer policy,
  frame denial, Server header stripped) using `?` set-if-absent so app headers win;
  `refresh-caddy-routes.sh` re-renders existing instances' routes with Caddy validation
  and automatic rollback.
- `doctor.sh` now also checks disk usage (tinymrp root + /var/lib/docker), per-domain TLS
  certificate expiry, backup timer presence, and backup freshness per instance.

### Security (Phase 3 — standalone Linux server, tier T2)
- New hardened nginx TLS site template (`deploy/server/nginx-tinymrp-site.conf`):
  HTTPS with modern TLS 1.2/1.3 ciphers, OCSP stapling, HTTP→HTTPS redirect with ACME
  passthrough, edge rate-limit zones for `/login` and `/api`, security headers snippet
  (correctly re-included per location), `client_max_body_size` aligned with upload caps,
  gzip. Certbot, internal-CA, self-signed and http-only variants supported. Validated
  with crossplane (nginx's official parser); compatible with distro nginx 1.18/1.24.
- `deploy/tinymrp.service` fully sandboxed: `ProtectSystem=strict`, `NoNewPrivileges`,
  `PrivateTmp/Devices`, kernel/namespace/personality restrictions, syscall filter
  (`@system-service`), empty capability set, writable paths limited to deliverables and
  `instance/`, resource guards, hardened gunicorn flags.
- New `deploy/scripts/install-server.sh`: idempotent scripted install of the manual path
  (packages incl. MongoDB 7.0 official repo, dedicated system user, venv, generated strong
  secrets with strict mode by default, systemd unit, nginx configs, UFW, optional fail2ban,
  journald cap, health self-check, canonical idempotent first-admin bootstrap).
- fail2ban filter + jail for login abuse (`deploy/server/fail2ban-*`), banning on
  repeated 401/403/429 login responses in the nginx access log.
- `deploy/server/README.md`: equivalent manual and scripted instructions plus
  post-install verification checklist.

### Security (Phase 2 — containers)
- App containers now run locked down: read-only root filesystem, `tmpfs /tmp`,
  `cap_drop: ALL`, `no-new-privileges`, health-gated startup ordering, healthchecks
  against `/api/health`. Applied to the single-host compose files AND the fleet
  instance template (`deploy/scripts/lib/common.sh`).
- Dockerfile hardened: dependency-first layer caching, no compiler toolchain in the
  final image, container HEALTHCHECK, gunicorn timeouts + worker recycling
  (`--max-requests` with jitter), access/error logs to stdout.
- No default admin credentials anywhere; the entrypoint refuses the historical
  example password and generates a one-time password when none is provided.
- Optional MongoDB authentication in the single-host compose (`MONGO_ROOT_USER`/
  `MONGO_ROOT_PASSWORD`; migration steps for existing volumes in
  docs/UPDATING_PRODUCTION.md).
- New `release-image` workflow: version tags build the image, gate on a trivy scan
  (HIGH/CRITICAL block), attach a CycloneDX SBOM, and publish to GHCR so hosts can
  deploy pre-built images via `update-instance.sh --image`.
- hadolint added to CI for the Dockerfile.

### Security (Phase 1)
- Rate limiting via Flask-Limiter: login/password endpoints throttled by default
  (`RATE_LIMIT_LOGIN`, default 10/min); optional global `/api` budget (`RATE_LIMIT_API`);
  Redis storage supported for multi-worker deployments (`RATE_LIMIT_STORAGE_URI`).
  429 responses are audit-logged.
- Tokenized file/extra-file links now EXPIRE (`FILES_TOKEN_TTL_SECONDS`, default 24 h).
  Legacy non-expiring tokens are only honored while `FILES_ALLOW_LEGACY_TOKENS=true`.
  NOTE: links copied/bookmarked before this release stop working unless the flag is set.
- Optional TOTP two-factor authentication (`SECURITY_TWO_FACTOR_ENABLED` +
  `SECURITY_TOTP_SECRETS`; `SECURITY_TWO_FACTOR_REQUIRED` to enforce). Default OFF.
- Structured logging with request IDs: `LOG_LEVEL`, `LOG_FORMAT=json|text`;
  `X-Request-ID` honored from the proxy and echoed on every response; auth events logged.
- Headers: `Referrer-Policy` upgraded to `strict-origin-when-cross-origin`;
  legacy `X-XSS-Protection` set to `0`; CSP `unsafe-inline` now removable via
  `TINYMRP_CSP_ALLOW_INLINE=false` (kept on until admin inline scripts are migrated).
- "Remember me" cookies capped at 7 days (`REMEMBER_COOKIE_DAYS`).

### Added
- Part detail: "Update files" now also removes registry entries whose backing file was deleted from
  storage (safe: skips when storage is unreachable, keeps files that still exist on disk).
- Part detail: "Delete part" gained an opt-in "Also delete related files from the server storage
  (permanent)" option covering artifacts, thumbnails, and extra files (records included), honoring
  BOM-children cascade. Only paths inside configured storage roots are ever touched.
- `VERSION` file; version is loaded at startup and reported by `/api/health` (`server_version`).
- Phase 0 professionalization (see `docs/PROFESSIONALIZATION_PLAN.md`): split runtime vs dev
  dependencies, `.dockerignore`, Dependabot, pre-commit hooks, CI jobs for pip-audit, CycloneDX SBOM,
  ShellCheck, and pytest coverage floor.

### Changed
- `requirements.txt` now contains runtime dependencies only (same pinned versions as previously
  deployed); all test/lint/supply-chain tooling moved to `requirements-dev.txt`.
  Newly declared runtime deps that were used but missing: `psutil`, `waitress`.
- `/downloads/macro` no longer falls back to the removed `OLD/` folder; the canonical macro lives at
  `app/static/misc/TinyMRP.swp`.

### Removed
- Dead code and repository fat: legacy `OLD/` tree, stale build logs, unused templates
  (`import/upload.html`, `tinylib/`), unused static JS editors, unused images (non-SVG), duplicate
  SolidWorks macros (`SOLIDSETUP/TinyMRP.swp`, `SOLIDSETUP/TinyMRP - Copy.swp`), tracked `__pycache__`
  artifacts (now untracked), and four unused Python imports.

## [2.0.0] — baseline

- Existing TinyMRP v2 application as deployed prior to this changelog's introduction.
