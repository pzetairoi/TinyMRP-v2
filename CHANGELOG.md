# Changelog

All notable changes to TinyMRP are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/).

## [Unreleased]

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
