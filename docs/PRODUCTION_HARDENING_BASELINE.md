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

Items 1-5 were statically or locally validated in Phase 0. Item 6 was blocked by
the legacy container role-seeding import at baseline and was closed by Phase 3A
on 2026-08-03. Existing Caddy routes and generated Compose configuration were
not removed or replaced.

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
| Python | CI/Docker target 3.11.15 | Phase 3C pinned-image suite on CPython 3.11.15 |
| Node.js | `.nvmrc` target 24; CI/image 24.18.1 | Clean frontend checks on 24.18.1 |
| npm | Lockfile-driven | 11.19.0 used for clean install |
| Docker Engine | Host tool | 25.0.3 |
| Docker Compose | Host tool | 2.24.6-desktop.1 |
| App base images | Node/Python tags plus manifest digests | `f70403e8...f7a6b3` / `b1899299...ad5cba` |
| Database image | `mongo:6.0@sha256:8b6d8f5b...bad3ac` | Static/guided/restore paths validated |
| Nginx image | `nginx:1.27-alpine@sha256:65645c7b...2f2a10` | Main and one-folder Compose validated |
| Caddy image | `caddy:2-alpine@sha256:5f5c8640...d58648` | Render, config and live proxy path validated |
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

## Phase 3A completion evidence (2026-08-03)

`DEPLOY-SEED-01` is closed on `hardening/production-readiness`. The container
entrypoint now delegates to a canonical, idempotent bootstrap service and exits
nonzero before the application command on invalid configuration or exhausted
runtime retries. Existing users, passwords, assignments, legacy roles and local
canonical-role drift are not rewritten.

Fresh-administrator credentials are explicit and originate operator-side. The
guided Caddy installer's persisted `.env` contract remains unchanged; the
one-folder and standalone installers now follow the same no-log, no-reset rule.
Direct Compose seeding defaults off. New administrators receive
`administrator`, while existing legacy `admin` assignments remain compatible.

Final verification evidence:

- Linux Python 3.11: `595 passed` on the final tree.
- Phase 3A focused suite: `26 passed` (20 bootstrap/installer plus six guided
  VPS/Caddy contract tests).
- Ruff, pinned Black, scoped mypy, Bandit `-ll`, `pip check`, Bash syntax,
  ShellCheck error-level, PowerShell parsing and workflow YAML/embedded Bash
  parsing passed.
- Main and one-folder Compose configurations parsed; the production image built.
- A real isolated fresh Compose stack verified Mongo availability, the exact
  canonical role set, administrator creation, CSRF browser login, public health,
  a protected bearer-token request, absence of the password from app logs and
  unchanged password hash/roles/counts after restart.
- A separate empty database with missing first-admin credentials exited `2` and
  did not launch the application command.
- A rendered internal-TLS Caddy route passed `caddy validate`; the rendered VPS
  Compose passed `docker compose config`; empty acceleration-prefix, isolated
  Mongo, update, rollback and doctor contracts are pinned by tests.

No public DNS, ACME account or live VPS was mutated. Those are release-environment
checks for Phase 10 rather than evidence of a remaining Phase 3A code defect.

## Phase 1B completion evidence (2026-08-03)

`IAM-TOKEN-01` is closed. New API tokens use a validated 90-day default and
365-day maximum, verify that their owner still exists and is active on every
request, expose expiry/last-use/status in user and administrator interfaces,
and support one-time-secret rotation plus explicit single/global revocation.
Existing no-expiry tokens remain usable but are labelled `legacy_no_expiry` so
operators can rotate deployed integrations without an unannounced outage.

The API-token portion of `IAM-REV-01` is closed: deactivation and ordinary,
administrator, CLI and disposable-test credential changes revoke every token
for the affected user. Browser-session invalidation was subsequently closed by
Phase 1C.

Final verification evidence:

- Ten new lifecycle regression tests; 71 focused lifecycle/auth/account/admin/
  CLI tests passed. The complete suite passed with `604 passed, 1 skipped` on
  the host and exited zero against the same mounted source in the production
  Python 3.11 image.
- Ruff, scoped mypy including the token service, pinned Black on the new/fully
  changed modules, Bandit `-ll`, `pip check`, frontend lint/build and gitleaks
  passed. Frontend lint retains one unrelated pre-existing warning.
- Main and one-folder Compose parsed. Bash syntax, ShellCheck error-level and
  PowerShell parsing passed. The rendered per-instance Compose and an internal-
  TLS Caddy route passed `docker compose config` and `caddy validate`.
- A newly built production image and isolated fresh stack verified canonical
  first-admin bootstrap, a default-expiring bearer token, browser login, public
  health, protected API access, restart continuity/idempotence, password log
  secrecy and fail-closed invalid bootstrap. The stack/volume were removed.
- The guided VPS/Caddy renderer was not rewritten: it still loads the instance
  environment, keeps `FILES_ACCEL_REDIRECT_PREFIX` empty, isolates Mongo and
  preserves update/rollback/doctor behavior through six regression contracts.

Residual Phase 1B risk: legacy no-expiry tokens remain valid until operators
rotate or revoke them; the UI makes them identifiable. Strict-mode browser
compatibility was closed by Phase 2, and add-in secret storage remains Phase 7.

## Phase 1C completion evidence (2026-08-03)

`IAM-REV-01` is closed. TinyMRP now uses Flask-Security's persisted
`fs_uniquifier` as a server-side browser-session version and rotates it with a
compare-and-set update whenever credentials or authorization state change. All
previous sessions and remember cookies stop resolving immediately; deleted and
inactive users continue to fail closed in Flask-Security's loader. Reactivation
rotates again, preventing a previously issued cookie from becoming valid later.

The control covers self-service, administrator and CLI password changes;
deactivation/reactivation; user role assignment and role-permission changes;
canonical role restoration; custom-role purge demotion; and disposable
permission-test/demo credential refreshes. Self-service password change signs
the current browser out explicitly. `session.security_event_revoke` audit events
record the target, reason and mechanism without recording either the previous or
replacement identifier.

Eleven regressions cover active, inactive/reactivated, deleted, expired-cookie,
explicitly revoked, self/admin/CLI password, role assignment/definition and
canonical-role restore cases. The affected security set passed 123 tests and the
complete host suite passed with `615 passed, 1 skipped`. The same combined tree
exited zero under the built Python 3.11 production image. Ruff, scoped mypy,
Bandit `-ll`, changed-file Black, Compose and deployment gates passed.

The protected Caddy path was unchanged. Main, one-folder and rendered guided-VPS
Compose configurations parsed; all deployment Bash/PowerShell scripts passed
syntax checks; ShellCheck passed at error level; the six Caddy/VPS contracts
passed; and a rendered internal-TLS route passed `caddy validate`.

## Phase 2 completion evidence (2026-08-03)

`AUTH-MODE-01` is closed by implementation checkpoint `80783b3` and this final
evidence checkpoint. Strict mode now classifies APIs explicitly as
browser-session, bearer-only integration, browser-or-bearer dual use,
capability-scoped public share, or anonymous health. The same-origin React UI
uses its session and retains origin/CSRF protection for unsafe requests; valid
API tokens cannot substitute for browser-only sessions. Invalid bearer headers
also cannot bypass the session origin guard.

Public shares expose only their capability-scoped part, BOM, files, document
pack and process metadata. Authentication and authorization failures use a
consistent nested JSON error envelope, and the React request layer reports
failures rather than silently turning protected data into empty datasets.
Application startup, main Compose, and newly created guided VPS/Caddy instances
default to strict. Compatibility mode remains explicit for local development,
time-bounded upgrades, and the plain-HTTP localhost/LAN one-folder helper; that
helper must not be exposed to the internet.

Final verification evidence:

- Seven new strict-mode integrations plus the affected session, bearer, share,
  permission, row-scope, bootstrap and six guided VPS/Caddy contracts passed.
  The focused final set passed 33 tests after pinning the one-folder profile.
- Frontend lint passed with its one pre-existing warning and the production
  bundle built. The pre-PDF combined host suite passed 622 tests with one skip.
- The final combined strict-auth plus pypdf tree passed **628 tests** under the
  production-derived Python 3.11 image. `pip check` was clean and the exact
  requirements audit remained one Flask-Security-Too finding in one package.
- Main and one-folder Compose parsed. All deployment Bash scripts passed syntax
  and ShellCheck error-level checks; PowerShell scripts parsed. The actual
  guided instance Compose renderer passed `docker compose config`, and its
  internal-TLS Caddy route passed `caddy validate`.
- The generated Caddy/Compose path, anonymous health check, empty
  `FILES_ACCEL_REDIRECT_PREFIX`, isolated Mongo network, and update/rollback/
  doctor contracts remain intact. No live VPS, DNS, or ACME state was changed.

Residual Phase 2 risk: `compat` remains available for controlled migration and
local plain-HTTP profiles, so operators can still weaken a production instance
by selecting it deliberately. Deployment documentation labels that choice and
the guided TLS installer writes strict mode for every new instance.

## Phase 3B advisory-triage evidence (2026-08-03)

The failing dependency gates were re-run and every current advisory was mapped
to reachable product features. At triage, `pip-audit` reported 34 rows across
five packages and the production frontend audit reported two high React Router
rows; triage alone did not close either gate.

Four Python findings had actionable remedies: Pillow 12.3.0, gunicorn 22.0.0
and cryptography 48.0.1 were straight runtime-pin upgrades and are now
integrated, and EOL `PyPDF2` was migrated to `pypdf` 6.14.2 across all 12
production import sites in `5743b82`. Pillow was highest priority because user-supplied images reach
native decoders; gunicorn's request-framing findings were relevant to the
protected Caddy reverse-proxy topology.

Two findings need explicit, time-limited exceptions if released before an
upstream/package migration is available. Flask-Security-Too's medium finding is
limited to WebAuthn, which TinyMRP does not enable or install. The React Router
high finding is limited to unstable RSC APIs, which the client-side SPA does not
use; the patched core `react-router` 8.3.0 release is not available as a
`react-router-dom` 8.x upgrade. `npm audit fix --force` proposes an unsafe
downgrade and must not be used. Both exception records remain **Proposed** until
a human risk owner supplies acceptance and expiry dates. Full evidence is in
`docs/security/dependency_advisory_triage.md` and
`docs/security/risk_acceptance_template.md`.

The three straight upgrades were integrated as `3346b51`: Pillow 12.3.0,
gunicorn 22.0.0 and cryptography 48.0.1, plus CFFI 2.0.0 required by
cryptography's resolver metadata. The production image built, `pip check`
passed, the complete combined Python 3.11 suite exited zero, and a disposable
Caddy-to-Gunicorn request returned healthy. The pypdf production build/full
suite, parity/adversarial regressions and protected Caddy gates also passed.
Requirements-file `pip-audit` now reports **1 finding in 1 package**: the
proposed Flask-Security-Too exception.

## Phase 3C supply-chain evidence (2026-08-03)

`SUPPLY-IMM-01` is closed. Every external GitHub Action is pinned to a verified
40-character commit, CI runners/toolchains are versioned (Python 3.11.15,
pip 26.2, Node 24.18.1, digest-pinned ShellCheck v0.11.0, Trivy v0.72.0 and
Syft v1.50.0), and Dockerfile plus
supported Mongo/Nginx/Caddy/MariaDB/Nextcloud defaults use verified multi-arch
manifest digests. The invalid `aquasecurity/trivy-action@0.36.0` reference was
corrected by pinning the peeled v0.36.0 commit. Update ownership and emergency
override rules are in `docs/security/supply_chain_policy.md`.

Python/npm/Trivy reports and backend/frontend-lockfile/final-image CycloneDX
SBOMs upload for 30 days before explicit blocking steps. The final Docker image
no longer runs `apt-get` or contains pip/setuptools/wheel. Pruning setuptools
removed its vulnerable vendored build tooling; Trivy v0.72.0 then reported
**0 HIGH and 0 CRITICAL** fixed findings.

Verification evidence:

- Nine workflow/Gitleaks contracts, actionlint with embedded ShellCheck, Bash
  syntax, and ShellCheck error-level passed. Node 24.18.1 clean install, expected
  npm-audit failure, frontend SBOM, lint and production build passed.
- Seven image-pin contracts plus six guided VPS/Caddy and twenty bootstrap
  contracts passed. Main, one-folder, rendered guided and rendered Nextcloud
  Compose passed; the digest-pinned internal-TLS route passed Caddy validation.
- The pinned production image `sha256:f4b9450b...c8399b` built successfully.
  The combined source tree
  passed **639 tests** in its production-derived Python 3.11.15 environment.
  A disposable pinned Mongo → TinyMRP → Caddy health request returned
  `{"ok":true,"security_mode":"strict"}` and cleaned up all test resources.
- Effective Gitleaks defaults are restored. A tracked-HEAD archive is clean;
  scanning 407 commits exits 1 with exactly two unsuppressed candidates in a
  deleted `.env.example`. They remain a release blocker pending classification
  and credential-rotation confirmation.

Phase 3C is engineering-complete for immutable image/action pins and retained
evidence, but release gates are not green: the two proposed dependency
exceptions lack human acceptance, the two historical secret candidates lack
human disposition, and Python artifact hashes remain future provenance work.

## Open production blockers

The identifier should be used in commits, reviews and risk decisions.

| ID | Priority | Status | Required phase | Blocker |
| --- | --- | --- | --- | --- |
| SEC-XSS-01 | P0 | Closed in `a7fa72d` | 1A | Stored XSS in job/order line rendering |
| SEC-CSP-01 | P1 | Open | 1A residual/2 | Inline scripts and handlers still require CSP `unsafe-inline` |
| IAM-REV-01 | P0 | Closed 2026-08-03 (`7cd50bd`) | 1C | API-token and browser-session revocation on credential/security-state changes |
| IAM-TOKEN-01 | P0 | Closed 2026-08-03 (`49cf24a`, `49ee2b4`) | 1B | Expiring token policy and complete token lifecycle controls |
| AUTH-MODE-01 | P0 | Closed 2026-08-03 (`80783b3`) | 2 | Strict browser, integration, public-share and health policies |
| DEPLOY-SEED-01 | P0 | Closed 2026-08-03 | 3A | Canonical, idempotent, fail-closed initialization and fresh-install smoke |
| SUPPLY-PY-01 | P0 | **Closed 2026-08-04** by accepted risk EXC-2026-001 (owner Francisco Quesada, expires 2026-11-02) | 3B | WebAuthn advisory is not applicable: WebAuthn is neither configured nor installed, and no patched release exists. Re-check at expiry. |
| SUPPLY-NPM-01 | P0 | **Closed 2026-08-04** by accepted risk EXC-2026-002 (owner Francisco Quesada, expires 2026-11-02) | 3B/6 | RSC-only advisory is not applicable: `frontend/src` uses no unstable RSC APIs. Fix exists in `react-router` 8.3.0 but `react-router-dom` has no 8.x; v8 migration tracked as Phase 6 frontend work. |
| SUPPLY-IMM-01 | P1 | Closed 2026-08-03 (`4984637`, `511555b`) | 3C | Base/deployment images and Actions pinned immutably |
| SUPPLY-SECRET-01 | P0 | **Closed 2026-08-04** by accepted risk EXC-2026-003 (owner Francisco Quesada, expires 2026-11-02) | 3C | `SECRET_KEY`/`SECURITY_PASSWORD_SALT` in `.env.example` (`e16f19d`) are publicly readable in history, but the owner confirmed no production server ever used them, so the exposure has no operational meaning. History rewrite (370 commits) judged not worth the cost. Deliberately NOT allowlisted — the gate still reports them. |
| SUPPLY-LOCK-01 | P1 | Open | 3C/8 | Python install artifacts lack `--require-hashes` provenance lock |
| IMPORT-DOS-01 | P0 | Open | 4A | No cumulative uncompressed/archive compression-ratio limit |
| IMPORT-ATOMIC-01 | P0 | Partially mitigated 2026-08-03; still Open | 4B | Cross-store imports can leave partial database/filesystem state. Durable journal, unique operation ID and compensating rollback of created parts are in. Still open: no MongoDB transactions, retries are not idempotent, and in-place modifications to pre-existing parts cannot be auto-restored (reported for manual reconciliation instead). |
| OPS-DBAUTH-01 | P0 | Partially mitigated 2026-08-04; still Open | 5 | Mongo authentication is optional/default-off in supported deployments. New guided instances now generate credentials and start authenticated; the rendered compose passes `MONGO_INITDB_ROOT_*` and `docker_compose_file` passes `--env-file` so interpolation actually resolves (it silently produced empty credentials before). Unauthenticated networked deployments now log a startup SECURITY warning, surface `mongodb_unauthenticated` on `/api/ready`, and can be made fail-closed with `TINYMRP_REQUIRE_MONGO_AUTH`. Still open: the app uses the root user rather than a least-privilege scoped user, existing instances are not migrated, the non-guided `docker-compose.yml` still defaults to empty credentials, and no live VPS install was executed. |
| OPS-HEALTH-01 | P0 | Partially mitigated 2026-08-03; still Open | 5 | Health endpoint does not prove database/storage readiness. `/api/ready` now verifies a real Mongo ping, file-root existence/writeability and a free-disk threshold, returning 503 when unusable; `/api/health` keeps its protected liveness contract. Still open: no authenticated diagnostics endpoint, and no orchestration consumes `/api/ready` yet (Compose/Caddy healthchecks and deploy scripts still poll `/api/health`). |
| OPS-RATE-01 | P1 | **Mitigated 2026-08-04** | 5 | In-memory/fail-open rate limiting across workers. `docker-compose.yml` now ships Redis and the app defaults to it, so limits are shared across gunicorn workers; the missing `redis` Python client (which made Redis config a silent no-op) is now pinned at 7.4.1. Failure policy is explicit via `RATE_LIMIT_FAIL_CLOSED` (default fail-open). Verified against a real Redis end to end. Still open: no per-endpoint budgets for expensive routes, `RATE_LIMIT_API` unset by default, and the guided VPS per-instance compose does not yet ship Redis. |
| ADDIN-TOKEN-01 | P0 | Open | 7 | Add-in token storage has plaintext and multi-user risks |
| ADDIN-SIGN-01 | P0 for external distribution | Open | 7 | Installer is unsigned |
| QA-FE-01 | P1 | Open | 6 | No frontend unit, browser or automated accessibility tests |
| COMM-SCOPE-01 | P0 for marketing | Open | 9 | Current product is an engineering BOM/document portal, not a complete MRP |
| COMM-LEGAL-01 | P0 for paid rollout | Open | 9 | Commercial/privacy/support/third-party notice package incomplete |

## Caddy/VPS-specific finding and resolution

At the Phase 0 baseline, the Caddy configuration and per-instance Compose
renderer were healthy, but the application image failed this entrypoint import:

```text
from app.views.admin_roles import PERMISSIONS
ImportError: cannot import name 'PERMISSIONS'
```

Phase 3A removed that inline import and legacy seed logic. The entrypoint now
retries only runtime failures, rejects deterministic operator errors immediately
and never starts Gunicorn after bootstrap failure. Guided instance creation still
writes explicit seed/email/password values, uses an empty
`FILES_ACCEL_REDIRECT_PREFIX`, waits for app health before installing its Caddy
route and preserves the update/automatic-rollback flow. Six cross-platform
contract tests plus rendered Compose/Caddy validation protect these behaviors.

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

Phase 2, Phase 3B engineering remediation, and Phase 3C immutable-pin/evidence
engineering are complete. Proposed vulnerability exceptions and historical
secret candidates still require human disposition. Phase 4A archive/resource
limits are the next engineering workstream.

## Residual Phase 0 limitations

- No external penetration, load, browser, accessibility or production restore
  test was performed.
- Caddy was validated in an isolated local configuration, not against a live
  VPS, DNS or ACME service.
- Phase 3A brought a real isolated fresh Compose stack online and validated the
  generated VPS/Caddy configuration, but did not mutate a live VPS, DNS or ACME
  environment.
- Image and Action content is immutable by default. Python package artifact
  hashes and GitHub-hosted runner internals remain reproducibility limits.
- The broad warning count, Black backlog and low-coverage modules remain later
  engineering-quality work.
