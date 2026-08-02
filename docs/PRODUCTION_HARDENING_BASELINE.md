# Production hardening baseline

Baseline date: 2026-08-02 (Australia/Sydney)

Branch: `hardening/production-readiness`

Baseline tag: `hardening-baseline-2026-08-02`

Application baseline inherited from `origin/main`: `f574515`

Phase 1A was committed concurrently as `a7fa72d` before Phase 0 completed. The
baseline tag therefore includes that stored-XSS remediation as well as the
Phase 0 changes described here.

## Purpose and production decision

This document freezes the evidence used to start the commercial hardening
roadmap. It is an engineering baseline, not a production approval. Public or
paid-customer production remains a no-go until the open production blockers in
this document and `hardeningplan.txt` are closed.

## Protected deployment requirement

The guided Ubuntu/VPS deployment under `deploy/scripts` uses a shared Caddy
reverse proxy. It is a supported, protected deployment path and must remain
operational throughout hardening.

Every phase that changes authentication, files, containers, health checks,
environment variables, networking, startup or deployment scripts must verify:

1. All deployment shell scripts still pass Bash syntax validation.
2. The host Caddyfile and a representative TinyMRP route render and pass
   `caddy validate` using the repository's configured Caddy image.
3. The generated per-instance Compose file passes `docker compose config`.
4. `FILES_ACCEL_REDIRECT_PREFIX` stays empty for the default Caddy path.
5. Existing-instance update and rollback behavior is preserved.
6. A fresh instance can bootstrap its roles and administrator and become ready.

Items 1-5 were statically or locally validated in Phase 0. Item 6 is currently
blocked by the legacy container role-seeding import and is the first priority
in Phase 3A. Existing Caddy routes and generated Compose configuration were not
removed or replaced by Phase 0.

## Baseline change classification

The repository was clean at `origin/main` when Phase 0 started except for the
untracked roadmap. The dependency and generated-bundle changes seen during the
earlier audit had already been deliberately committed:

| Commit | Classification | Phase 0 decision |
| --- | --- | --- |
| `5a893e6` | Dependabot-derived Actions, Python tooling/runtime minors, frontend dependency minors, rebuilt tracked bundle | Preserve as intentional |
| `f574515` | Dev-only `globals` update | Preserve as intentional |
| `a7fa72d` | Phase 1A stored-XSS remediation and 17 regression tests | Preserve; completed ahead of sequence |

Phase 0 added narrowly scoped baseline corrections:

- `.gitattributes` forces LF for frontend inputs, generated frontend assets and
  Linux shell scripts, preventing Windows checkout line endings from creating
  spurious frontend build changes.
- Runtime-secret lock acquisition now creates its missing parent directory,
  allowing a truly clean checkout or new compat-mode instance to start.
- Flask-Security cache directives use standards-compliant token values with the
  pinned Werkzeug release, producing `private, no-store` instead of
  `private=True, no-store=True`.
- Regression tests cover the missing runtime-secret directory and semantic
  cache-control behavior.

## Declared and observed versions

| Component | Declared/release value | Phase 0 observation |
| --- | --- | --- |
| Application | `VERSION` = 2.0.0 | 2.0.0 |
| Python | CI/Docker target 3.11 | Clean tests on CPython 3.11.11 |
| Node.js | `.nvmrc`/CI/Docker target 24 | Clean frontend checks on 24.18.1 |
| npm | Lockfile-driven | 11.19.0 used for clean install |
| Docker Engine | Host tool | 25.0.3 |
| Docker Compose | Host tool | 2.24.6-desktop.1 |
| App base images | `node:24-alpine`, `python:3.11-slim-bookworm` | Image build passed; tags remain mutable until Phase 3C |
| Database image | `mongo:6.0` | Locally resolved digest `sha256:95ec2fde...ff03a` |
| Nginx image | `nginx:1.27-alpine` | Locally resolved digest `sha256:65645c7b...f2a10` |
| Caddy image | `caddy:2-alpine` | Validated digest `sha256:5f5c8640...58648` |
| SolidWorks installer | 1.0.2 | `TinyMRP_SolidWorksAddin_1.0.2_20260802_112728.exe` |
| Add-in assembly/build | 1.0.0 / build file | Build number 346; Debug test run did not increment it |

The application, installer and assembly versions are not aligned. This remains
Phase 7 work.

## Dependency state

Runtime Python packages and development tools are exact-pinned. Frontend
dependency intent uses semver ranges, while `package-lock.json` is the resolved
install source.

Baseline SHA-256 values:

- `requirements.txt`: `181440EFBBA31485CED5D751A45BFA9D1A395082D21772DA5E118BE3EE1D7479`
- `requirements-dev.txt`: `58493FDE3C16BF7EEC32C2894A776DAE8F9E21829C63B9D328E089C5D82D6C0A`
- `frontend/package-lock.json`: `D6E45A850995B57139BF9669C523B308F82BE0EA239E32A8E2FFC78D16B94E67`

A clean Python 3.11 environment installed 118 packages and passed dependency
compatibility checking. A clean frontend install audited 269 packages.

## Verification record

| Check | Result | Notes |
| --- | --- | --- |
| Backend full suite | PASS | 568 passed, 1 skipped, 585 warnings |
| Backend coverage | PASS against current gate | 71.04%; gate is 55% |
| Missing runtime-secret parent regression | PASS | Clean nested path created and persisted |
| Ruff configured rules | PASS | Current narrow rule selection only |
| Mypy configured scope | PASS | Two explicitly configured modules only |
| Bandit `-ll` | PASS | No medium/high findings; template XSS is outside Bandit's coverage |
| Black | FAIL/non-blocking | 162 files would be reformatted |
| Frontend clean install | PASS | Node 24/npm 11, lockfile install |
| Frontend lint | PASS with warning | One unused eslint-disable warning |
| Frontend build | PASS | Main chunk about 1.31 MB; 3MF chunk about 591 KB |
| Consecutive frontend builds | PASS | Second build caused zero byte changes |
| Production Docker image | PASS | Local image ID `sha256:91f92cb9...ba795`, about 336 MB |
| Main Compose config | PASS | Required test environment supplied |
| One-folder Compose config | PASS | Required deliverables path supplied |
| Deployment shell syntax | PASS | `deploy/scripts/*.sh`, libraries and entrypoint |
| Rendered Caddy config | PASS | Isolated `internal-tls` route passed `caddy validate` |
| Rendered VPS instance Compose | PASS | Repository renderer output passed Compose config |
| SolidWorks add-in tests | PASS | 62/62 in Debug; build number stayed 346 |
| Installer signature | FAIL | Authenticode status `NotSigned` |
| Backend SBOM generation | PASS | CycloneDX command completed; release attachment remains Phase 3C |
| Python vulnerability gate | FAIL | 34 advisory entries across 5 packages |
| Frontend production vulnerability gate | FAIL | 2 high-severity React Router advisory entries |

Installer SHA-256:
`E07FD3DA76FAA3A81A69F7B371A2894F9169646A34247747D11076A71EBE908B`.

## Open production blockers

The identifier should be used in commits, reviews and risk decisions.

| ID | Priority | Status | Required phase | Blocker |
| --- | --- | --- | --- | --- |
| SEC-XSS-01 | P0 | Closed in `a7fa72d` | 1A | Stored XSS in job/order line rendering |
| SEC-CSP-01 | P1 | Open | 1A residual/2 | Inline scripts and handlers still require CSP `unsafe-inline` |
| IAM-REV-01 | P0 | Open | 1B/1C | Deactivated users and credential changes do not reliably revoke API/session access |
| IAM-TOKEN-01 | P0 | Open | 1B | User tokens default to no expiry and lack complete lifecycle controls |
| AUTH-MODE-01 | P0 | Open | 2 | Strict mode is incompatible with normal browser and public-share API flows |
| DEPLOY-SEED-01 | P0 | Open; next deployment priority | 3A | Entrypoint imports removed `PERMISSIONS`, retries, then starts without successful seeding |
| SUPPLY-PY-01 | P0 | Open | 3B | Python vulnerability gate reports 34 entries in 5 packages |
| SUPPLY-NPM-01 | P0 | Open | 3B | Frontend production audit reports 2 high entries |
| SUPPLY-IMM-01 | P1 | Open | 3C | Base images and Actions are not pinned to immutable digests/SHAs |
| IMPORT-DOS-01 | P0 | Open | 4A | No cumulative uncompressed/archive compression-ratio limit |
| IMPORT-ATOMIC-01 | P0 | Open | 4B | Cross-store imports can leave partial database/filesystem state |
| OPS-DBAUTH-01 | P0 | Open | 5 | Mongo authentication is optional/default-off in supported deployments |
| OPS-HEALTH-01 | P0 | Open | 5 | Health endpoint does not prove database/storage readiness |
| OPS-RATE-01 | P1 | Open | 5 | In-memory/fail-open rate limiting across workers |
| ADDIN-TOKEN-01 | P0 | Open | 7 | Add-in token storage has plaintext and multi-user risks |
| ADDIN-SIGN-01 | P0 for external distribution | Open | 7 | Installer is unsigned |
| QA-FE-01 | P1 | Open | 6 | No frontend unit, browser or automated accessibility tests |
| COMM-SCOPE-01 | P0 for marketing | Open | 9 | Current product is an engineering BOM/document portal, not a complete MRP |
| COMM-LEGAL-01 | P0 for paid rollout | Open | 9 | Commercial/privacy/support/third-party notice package incomplete |

## Caddy/VPS-specific finding

The Caddy configuration and per-instance Compose renderer are healthy at this
baseline. The application image itself still fails this import used by its
entrypoint:

```text
from app.views.admin_roles import PERMISSIONS
ImportError: cannot import name 'PERMISSIONS'
```

The entrypoint retries and eventually starts the application, which can delay
updates and leave fresh instances without expected roles/admin bootstrap. Do
not interpret a successful image build or valid Caddyfile as a successful fresh
deployment. Repair and smoke-test this in Phase 3A before relying on new VPS
instance creation.

## Handoff rules

1. Read this document and the status block at the top of `hardeningplan.txt`.
2. Work only on `hardening/production-readiness` unless the owner selects a new
   branch.
3. Do not rewrite or delete the Caddy deployment path. Treat its six checks
   above as compatibility tests.
4. Keep one concern per commit and update the roadmap status after every commit.
5. Do not claim a production gate is closed solely because unit tests pass.
6. Re-run the complete backend suite after security or authorization changes.
7. Use Python 3.11 and Node 24 for release evidence, regardless of host defaults.
8. Preserve the baseline tag; do not move or recreate it.

The recommended next implementation is Phase 3A because the owner explicitly
requires the VPS/Caddy deployment workflow to remain usable. After Phase 3A,
resume Phase 1B/1C and Phase 2 unless new evidence changes the dependency order.

## Residual Phase 0 limitations

- No external penetration, load, browser, accessibility or production restore
  test was performed.
- Caddy was validated in an isolated local configuration, not against a live
  VPS, DNS or ACME service.
- The generated VPS instance was not brought fully online because the known
  entrypoint seeding defect belongs to Phase 3A.
- Mutable image tags mean the locally observed digests are evidence, not a
  reproducible release guarantee.
- The broad warning count, Black backlog and low-coverage modules remain later
  engineering-quality work.
