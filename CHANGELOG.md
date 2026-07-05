# Changelog

All notable changes to TinyMRP are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/).

## [Unreleased]

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
