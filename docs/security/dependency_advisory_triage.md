# Dependency advisory triage

Workstream: **P3B-ADVISORY-TRIAGE** · Phase 3B · blockers `SUPPLY-PY-01`, `SUPPLY-NPM-01`

Evidence was originally collected **2026-08-03** against commit `de8d5a5` on
`hardening/production-readiness`. The audit counts, advisory state, package
availability and source applicability were independently revalidated after
Phase 1B and before integration in commit `50d75e7`.

The original triage commit was **analysis only**. This document now also records
the reviewed remediation status after runtime upgrade commit `3346b51`, while
preserving the applicability evidence that drove each decision.

## How this was produced

```
pip-audit -r requirements.txt --format json     # 34 entries / 5 packages
cd frontend && npm audit --omit=dev --audit-level=high   # 2 high entries
```

After `3346b51`, the same Python audit reports **2 findings / 2 packages**.
The frontend result remains 2 high entries because its separately proposed
exception and framework migration have not changed.

Advisory detail was pulled from the GitHub Advisory API and OSV. Applicability
was then checked against the source tree; every claim below cites what was
inspected.

> Counts match the Phase 0 baseline (`docs/PRODUCTION_HARDENING_BASELINE.md`):
> Python 34 entries across 5 packages, frontend 2 high entries.

## Summary

| Package | Pinned | Entries | Applicable? | Remedy | Blocked? |
| --- | --- | --- | --- | --- | --- |
| pillow | **12.3.0** | 0 | Was applicable | **remediated in `3346b51`** | no |
| cryptography | **48.0.1** + CFFI 2.0.0 | 0 | Was partly applicable | **remediated in `3346b51`** | no |
| gunicorn | **22.0.0** | 0 | Was conditional on proxy topology | **remediated in `3346b51`** | no |
| PyPDF2 | 3.0.1 | 1 | Yes, low | **package rename → `pypdf`** | needs code change |
| Flask-Security-Too | 5.8.1 | 1 | **NO — feature not enabled** | none available | exception |
| react-router(-dom) | 7.18.1 | 2 | **NO — unstable RSC APIs only** | none reachable | exception |

Net after the straight upgrades: the Python audit is down from **34/5 to 2/2**.
PyPDF2 still needs its separately tested package migration, while
Flask-Security-Too and React Router retain proposed (not accepted) exceptions.

---

## 1. Pillow 11.3.0 → 12.3.0 — REMEDIATED

**Remedy: upgrade to `pillow==12.3.0`.** Verified installable
(`pip install --dry-run pillow==12.3.0` succeeds).

**Implemented in `3346b51`.** The image/upload/docpack/markup-focused set passed
124 tests on Python 3.11; the complete combined hardening tree also exited zero.

### Why it applies

These are memory-safety defects (out-of-bounds write, integer overflow, native
heap corruption) reachable by decoding a **crafted image**. TinyMRP decodes
images that arrive from users:

- `app/services/upload_pack.py:158` — `Image.open(io.BytesIO(source["bytes"]))`
  on uploaded pack contents.
- `app/services/thumbs_gen.py:86` — `Image.open(src_abs)` for thumbnail
  generation.
- `app/services/markup_documents.py:212` — `Image.open(source_path)`.
- `app/services/docpacks.py:1082` — PIL import for docpack rendering.

Representative entries:

| Advisory | CVE | Trigger | Fixed in |
| --- | --- | --- | --- |
| PYSEC-2026-2249 | CVE-2026-25990 | out-of-bounds write on crafted **PSD** | 12.1.1 |
| PYSEC-2026-165 | CVE-2026-42308 | integer overflow on extreme **font glyph advance** | 12.2.0 |
| PYSEC-2026-3453 | CVE-2026-59205 | heap corruption via `ImageCms` transform mode mismatch | 12.3.0 |

12.3.0 covers the whole set (highest required fix version among the 25).

### Assessment

This is the one Python finding that maps to a real, remotely-reachable attack
path in this product, because upload is a core workflow. It should be treated as
the priority item of Phase 3B rather than being averaged into a count of 34.

### Verification performed with the upgrade

The image-touching suites covered thumbnail generation, docpack rendering,
markup documents and upload-pack import in addition to the aggregate suite. The
pinned `reportlab`/`svglib` combination remained compatible.

---

## 2. cryptography 43.0.1 → 48.0.1 — REMEDIATED

**Remedy: upgrade to `cryptography==48.0.1`.** Verified installable.

**Implemented in `3346b51`.** Resolver testing exposed a required compatibility
change: cryptography 48.0.1 requires `cffi>=2.0.0`, so the prior exact CFFI
1.17.1 pin produced `ResolutionImpossible`. CFFI 2.0.0 was upgraded in the same
runtime-only commit; Argon2, `pip check`, and the complete suite passed.

| Advisory | CVE | Note | Fixed in |
| --- | --- | --- | --- |
| GHSA-537c-gmf6-5ccf | — | statically-linked **OpenSSL** in PyPI wheels (CVSS 7.5) | 48.0.1 |
| PYSEC-2026-1284 | CVE-2024-12797 | OpenSSL RFC7250 handshake issue | 44.0.1 |
| PYSEC-2026-35 | CVE-2026-34073 | — | 46.0.6 |
| PYSEC-2026-2141 | CVE-2026-26007 | — | 46.0.5 |

`pip-audit` emits five rows because `PYSEC-2026-35` is duplicated in its current
output; there are four distinct advisory IDs. The bundled-OpenSSL advisory
applies to anyone installing the PyPI wheel, which is what the container does.
48.0.1 supersedes every reported row.

Exposure is lower than Pillow's: `cryptography` here backs password hashing and
TLS client work rather than parsing hostile input directly. Still, it is a clean
upgrade with no code change, so there is no reason to defer it.

---

## 3. gunicorn 21.2.0 → 22.0.0 — REMEDIATED

**Remedy: upgrade to `gunicorn==22.0.0`.** Verified installable.

**Implemented in `3346b51`.** Gunicorn's configuration check passed, all six
guided VPS/Caddy contracts and rendered configurations passed, and an actual
disposable Caddy → Gunicorn 22 → TinyMRP health request returned successfully.

| Advisory | CVE | Issue | Fixed in |
| --- | --- | --- | --- |
| PYSEC-2026-1434 | CVE-2024-1135 | HTTP **request smuggling** via `Transfer-Encoding` handling | 22.0.0 |
| PYSEC-2026-1433 | CVE-2024-6827 | improper `Transfer-Encoding` validation | 22.0.0 |

Request smuggling matters when a proxy sits in front of the app and the two
disagree about request framing. **The supported deployment puts Caddy in front of
gunicorn**, so this topology is exactly the one these advisories concern.

Note gunicorn is the Linux/container server only; the Windows service path uses
`waitress`, which is unaffected.

Because Caddy is a protected supported path (see the roadmap's protected-owner
requirement), validate a rendered VPS/Caddy deployment after this upgrade.

---

## 4. PyPDF2 3.0.1 — 1 advisory — APPLICABLE, needs a code migration

| Advisory | CVE | Issue | "Fixed in" |
| --- | --- | --- | --- |
| PYSEC-2026-1835 | CVE-2023-36464 | infinite loop / DoS on crafted PDF | 3.9.0 |

**There is no PyPDF2 3.9.0.** Confirmed: the last PyPDF2 release is **3.0.1**
(`pip install pypdf2==3.9.0` → "No matching distribution found", available
versions end at 3.0.1). The project was renamed, and the advisory's fix version
refers to the successor package **`pypdf`**. PyPDF2 is end-of-life.

So this cannot be closed by a version bump; it needs a dependency swap plus an
import migration across 12 call sites:

- `app/services/docpacks.py` — lines 1490, 2174, 2256, 2274, 2299, 3093, 3214
- `app/services/markup_documents.py` — line 333
- `app/services/order_scope.py` — lines 166, 188, 240, 293

The imported names (`PdfReader`, `PdfWriter`, `PdfMerger`) exist in `pypdf` with
largely compatible APIs, so the migration is mechanical but touches PDF
generation — the docpack/binder path, which has substantial test coverage.

**Recommendation:** track separately from the straight upgrades. Applicability is
real (crafted PDFs are user-supplied) but severity is DoS-only, so it should not
hold up the Pillow/cryptography/gunicorn work.

---

## 5. Flask-Security-Too 5.8.1 — 1 advisory — NOT APPLICABLE

`GHSA-f66q-9rf6-8795` — *WebAuthn reauthentication freshness bypass via
cross-user assertion*. Severity **medium**. Affected `>= 5.8.0, <= 5.8.1`.
**No patched version exists** (`first_patched_version: null`); upstream `main`
was still unfixed when the advisory was published.

### Why it does not apply

The defect is entirely on the **WebAuthn reauthentication path**
(`webauthn.py`). TinyMRP does not enable WebAuthn:

- No `SECURITY_WEBAUTHN*` configuration anywhere in `app/` (grep: no matches).
- `requirements.txt:22` pins `Flask-Security-Too==5.8.1` **with no extras**, so
  the optional WebAuthn dependencies are not installed at all.
- The only multi-factor path implemented is TOTP, gated behind
  `SECURITY_TWO_FACTOR_ENABLED` (`app/__init__.py:390-418`), default off.

The vulnerable code path is unreachable in this deployment. Exploitation also
requires an authenticated attacker who already holds a registered WebAuthn
credential on the same deployment — impossible when the feature is off.

**Action: risk acceptance, not an upgrade.** Since no fix exists, this is a
standing exception that must be revisited when upstream ships one. See
`risk_acceptance_template.md` for the record to file.

**Compensating control:** treat "do not enable WebAuthn" as a security
constraint, not a preference. If WebAuthn is ever enabled, this advisory becomes
immediately applicable and blocking.

---

## 6. react-router / react-router-dom — 2 high entries — NOT APPLICABLE

`GHSA-qwww-vcr4-c8h2` — *RSC Mode CSRF Bypass Allows Action Execution Before 400
Response*. Severity **high**. Follow-up to CVE-2026-22030.

### Why it does not apply

The advisory states plainly: **"This only affects your application if you are
using the unstable RSC APIs."** TinyMRP does not.

- No `unstable_*`, `@react-router/server` or RSC imports anywhere in
  `frontend/src` (grep: no matches).
- Every import is from the stable `react-router-dom` entry point.

The app is a client-side SPA using standard routing. There is no React Server
Components mode to bypass.

### Why the gate still fails — corrected finding

The advisory range is `>= 7.12.0, < 8.3.0`, and **`react-router` 8.3.0 does
contain the fix**. However:

| Package | Latest published | Patched release available? |
| --- | --- | --- |
| `react-router` (core) | **8.3.0** | yes |
| `react-router-dom` (used here) | **7.18.2** | **no — no 8.x exists** |

`react-router-dom@8.3.0` returns HTTP 404 from the registry. The v8 line ships
under the core `react-router` package only; `react-router-dom` was not carried
forward. So the patched version is genuinely unreachable for this dependency
without migrating the app from `react-router-dom` to `react-router` v8 — a
framework migration, not a version bump.

`npm audit fix --force` proposes downgrading to `react-router-dom@7.11.0`. **Do
not do this**: 7.11.0 carries five *other* react-router advisories (DoS via
reflected input, CSRF in action processing, open redirect, constructor injection
via `deserializeErrors`, DoS via inefficient route matching). The current pin is
strictly the better position.

> This supersedes the earlier note in `hardeningplan.txt` that said no fixed
> version existed. A fix exists upstream — it is simply not published for the
> package this application depends on.

**Action: risk acceptance with a migration-tracking item.** The correct long-term
remedy is the `react-router` v8 migration, which belongs with the frontend work
in Phase 6 rather than in a dependency-bump commit.

---

## Recommended Phase 3B sequencing

Ordered by real risk, not by advisory count:

1. **DONE — `pillow` → 12.3.0** — image/docpack/upload suites passed.
2. **DONE — `gunicorn` → 22.0.0** — rendered and live disposable Caddy paths
   passed.
3. **DONE — `cryptography` → 48.0.1 + CFFI 2.0.0** — resolver, Argon2 and full
   suite passed.
4. **`PyPDF2` → `pypdf`** — separate commit; 12 import sites, DoS-only severity.
5. **File two risk acceptances** — Flask-Security-Too (WebAuthn off) and
   react-router (RSC unused).

Keep runtime and dev-tooling upgrades in separate commits — the roadmap asks for
this and the earlier batch on `main` did not honour it.

### Remaining scope

- `SUPPLY-PY-01` and `SUPPLY-NPM-01` remain open. After items 1–3, the
  Python gate reports only PyPDF2 and Flask-Security-Too; completing item 4
  should leave only Flask-Security-Too.
- Even after item 4, the
  Python gate still reports the Flask-Security-Too entry and the frontend gate
  still reports the two react-router entries, because neither has a reachable
  fix. **Those gates cannot go green by upgrading alone** — they need the filed
  exceptions plus, if the gate must be blocking, an explicit ignore entry
  referencing the accepted-risk record.

## Re-check triggers

- Flask-Security-Too publishes any release above 5.8.1 → re-assess immediately.
- `react-router-dom` publishes an 8.x, or the app migrates to `react-router` v8.
- Any change that enables WebAuthn → the Flask-Security exception is void.
- Any change that adopts React Router RSC APIs → the react-router exception is void.
- Re-run both gates before every release regardless; the latest 2026-08-03
  Python snapshot is 2 findings across 2 packages.
