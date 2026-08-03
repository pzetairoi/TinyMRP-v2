# Vulnerability-gate exception / risk acceptance

Workstream: **P3B-ADVISORY-TRIAGE** · Phase 3B · created 2026-08-03

The roadmap requires every vulnerability-gate exception to carry an
**applicability analysis, compensating controls, an owner and an expiry date**.
This file provides that record format and holds the two exceptions TinyMRP
currently needs.

## Rules

1. **An exception is a last resort.** If a fixed version exists and is reachable,
   upgrade instead. See `dependency_advisory_triage.md` — most current findings
   are ordinary upgrades and must not be exception-ed away.
2. **Exceptions expire.** No open-ended acceptances. An expired record is a
   release blocker until it is re-reviewed and re-approved.
3. **An exception is void the moment its stated assumption breaks.** Each record
   names the condition that invalidates it. That condition is a security
   constraint, not a preference.
4. **The named owner is a person**, not a team, and is accountable for the
   re-check.
5. If a blocking gate must be suppressed to ship, the ignore entry in CI must
   reference the exception ID — never a bare ignore.

## Record format

```
### <EXC-ID>

| Field | Value |
| --- | --- |
| Advisory | <GHSA/PYSEC/CVE id + link> |
| Package / version | <name> <pinned version> |
| Severity (upstream) | <critical/high/medium/low + CVSS if published> |
| Gate | <pip-audit | npm audit | trivy> |
| Blocker ID | <e.g. SUPPLY-PY-01> |
| Status | Proposed / Accepted / Expired / Withdrawn |
| Owner | <name> |
| Accepted on | <YYYY-MM-DD> |
| Expires | <YYYY-MM-DD — max 90 days unless justified> |

**Applicability analysis** — is this deployment actually affected? Cite the
code/config inspected. State the reachable path, or why there is none.

**Why no upgrade** — no fix published / fix unreachable for this package /
fix requires a migration tracked as <item>.

**Compensating controls** — what limits exposure meanwhile.

**Voiding conditions** — what makes this exception immediately invalid.

**Re-check plan** — what is checked at expiry, by whom.
```

---

## Active exceptions

All three records below are **Accepted**, signed by Francisco Quesada on
2026-08-04 and expiring **2026-11-02**. The applicability evidence is in
`dependency_advisory_triage.md` and `secret_scanning_review.md`.

### Review queue — what to fix when these expire

Ordered by what actually removes the exception rather than renewing it:

| ID | Fix that closes it | Blocked on |
| --- | --- | --- |
| EXC-2026-002 | migrate `react-router-dom` → `react-router` v8 | upstream published no `react-router-dom` 8.x; belongs with Phase 6 frontend work |
| EXC-2026-001 | upgrade past `Flask-Security-Too` 5.8.1 | no patched release exists yet |
| EXC-2026-003 | nothing to fix; re-confirm no deployment used the values | n/a — closes permanently once re-confirmed |

At expiry, re-run both gates and re-check each advisory for a published fix. If
a fix exists, **upgrade instead of renewing**.

### EXC-2026-001 — Flask-Security-Too WebAuthn reauthentication bypass

| Field | Value |
| --- | --- |
| Advisory | [GHSA-f66q-9rf6-8795](https://github.com/advisories/GHSA-f66q-9rf6-8795) |
| Package / version | `Flask-Security-Too` 5.8.1 (`requirements.txt:22`) |
| Severity (upstream) | Medium |
| Gate | pip-audit |
| Blocker ID | SUPPLY-PY-01 |
| Status | **Accepted** |
| Owner | Francisco Quesada (fcoquesada@gmail.com) |
| Accepted on | 2026-08-04 |
| Expires | **2026-11-02** (90 days) |

**Applicability analysis.** Not applicable to this deployment. The defect is on
the WebAuthn reauthentication path (`webauthn.py`): a session is marked
reauthentication-fresh after a WebAuthn assertion whose credential belongs to a
different user. TinyMRP does not enable WebAuthn:

- No `SECURITY_WEBAUTHN*` key is set anywhere in `app/`.
- `Flask-Security-Too==5.8.1` is pinned **without extras**, so the optional
  WebAuthn dependencies are not installed.
- The only MFA path is TOTP, behind `SECURITY_TWO_FACTOR_ENABLED`
  (`app/__init__.py:390-418`), default off.

Exploitation additionally requires an authenticated attacker already holding a
registered WebAuthn credential on the same deployment — unobtainable with the
feature disabled.

**Why no upgrade.** No fixed version exists. The advisory records
`first_patched_version: null`, and upstream `main` was still unfixed at
publication. Affected range `>= 5.8.0, <= 5.8.1` covers the current pin, and
there is nothing above it to move to.

**Compensating controls.**
- WebAuthn stays disabled; treat this as a security constraint.
- No optional WebAuthn dependency is installed, so the code path cannot execute.
- TOTP remains the supported second factor.

**Voiding conditions.**
- Any change that enables WebAuthn, or installs Flask-Security WebAuthn extras.
- Publication of any Flask-Security-Too release above 5.8.1 → upgrade instead of
  renewing.

**Re-check plan.** At expiry, re-run `pip-audit -r requirements.txt` and check
the advisory for a patched version. If one exists, upgrade and withdraw this
record.

---

### EXC-2026-002 — React Router RSC-mode CSRF bypass

| Field | Value |
| --- | --- |
| Advisory | [GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2) |
| Package / version | `react-router-dom` 7.18.1 → `react-router` 7.x (`frontend/package.json`) |
| Severity (upstream) | High |
| Gate | npm audit (`--omit=dev --audit-level=high`) |
| Blocker ID | SUPPLY-NPM-01 |
| Status | **Accepted** |
| Owner | Francisco Quesada (fcoquesada@gmail.com) |
| Accepted on | 2026-08-04 |
| Expires | **2026-11-02** (90 days) |

**Applicability analysis.** Not applicable. The advisory states it "only affects
your application if you are using the unstable RSC APIs." TinyMRP does not:

- No `unstable_*`, `@react-router/server` or RSC imports in `frontend/src`.
- All routing imports come from the stable `react-router-dom` entry point.
- The frontend is a client-side SPA; there is no React Server Components mode
  to bypass.

**Why no upgrade.** The fix exists but is **unreachable for this package**. The
advisory range is `>= 7.12.0, < 8.3.0` and `react-router` (core) 8.3.0 is
patched — but `react-router-dom` has no 8.x at all (latest 7.18.2;
`react-router-dom@8.3.0` 404s). The v8 line ships under the core package only.
Reaching the fix means migrating the app off `react-router-dom` onto
`react-router` v8 — a framework migration, appropriate to Phase 6 frontend work,
not a dependency bump.

**Do not run `npm audit fix --force`.** It proposes `react-router-dom@7.11.0`,
which carries five other advisories (DoS via reflected input, CSRF in action
processing, open redirect via backslash, arbitrary constructor injection in
`deserializeErrors`, DoS via inefficient route matching). The current pin is the
safer position; downgrading trades one inapplicable finding for five applicable
ones.

**Compensating controls.**
- RSC APIs are not used, and adopting them requires a deliberate code change.
- The app is same-origin with CSRF protection on session-authenticated state
  changes (existing Flask-WTF configuration).
- The current pin already reduced the count from five react-router advisories to
  one.

**Voiding conditions.**
- Any adoption of React Router RSC / `unstable_*` APIs.
- Publication of a patched `react-router-dom` 8.x, or completion of the
  `react-router` v8 migration → upgrade and withdraw.

**Re-check plan.** At expiry, re-run `npm audit --omit=dev --audit-level=high`
and check whether `react-router-dom` has published an 8.x. Track the v8
migration as frontend work.

---

### EXC-2026-003 — Historical secrets in git history

| Field | Value |
| --- | --- |
| Finding | `SECRET_KEY` and `SECURITY_PASSWORD_SALT` in `.env.example`, commit `e16f19d` (2025-08-16) |
| Gate | gitleaks (full-history scan) |
| Blocker ID | SUPPLY-SECRET-01 |
| Status | **Accepted** |
| Owner | Francisco Quesada (fcoquesada@gmail.com) |
| Accepted on | 2026-08-04 |
| Expires | **2026-11-02** (90 days) |

**Applicability analysis.** Two real high-entropy values were committed in the
repository's initial commit and remain reachable from git history. The
repository is **public**, so they have been publicly readable since 2025-08-16.

The exposure is nevertheless worthless: **the owner has confirmed no production
server ever used these values.** They were an example file. A `SECRET_KEY` that
never signed a session and a `SECURITY_PASSWORD_SALT` that never salted a stored
password grant an attacker nothing.

The file was deleted (`ff020f2` / `114059c`); neither value appears in `HEAD` or
the working tree.

**Why no remediation.** Purging them requires rewriting history with
`git filter-repo` or BFG. That rewrites **all 370 commits**, changes every
commit hash, and forces every clone and open branch to be recreated — including
the Dependabot branches. That cost is not justified for values with no
operational meaning. Rotation is likewise a no-op: there is nothing deployed to
rotate.

**Compensating controls.**
- `.gitignore` covers `.env`, `.env.local` and `.env.*.local`, so a real
  environment file cannot be committed the same way again.
- Secret scanning is now genuinely effective (it previously detected nothing —
  see `secret_scanning_review.md`), so a *new* leak would be caught.
- The two findings are deliberately **not allowlisted**. The gate continues to
  report them, which is the intended behaviour: this record is the disposition,
  not a suppression.

**Voiding conditions.**
- Discovery that any deployment did use these values → rotate immediately and
  treat as a live incident.
- Any *new* secret appearing in history → this record does not cover it.

**Re-check plan.** At expiry, re-confirm no deployment ever used these values.
Once that is confirmed a second time, this can be closed permanently rather
than renewed; the underlying facts cannot change.

---

## Remediation status — do not create exceptions for these

Listed so nobody files an unnecessary acceptance. Detail in
`dependency_advisory_triage.md`.

| Package | Action | Note |
| --- | --- | --- |
| `pillow` 11.3.0 | **done** → 12.3.0 (`3346b51`) | 25 applicable upload-decoder rows cleared |
| `cryptography` 43.0.1 | **done** → 48.0.1 + CFFI 2.0.0 (`3346b51`) | bundled-OpenSSL and related rows cleared |
| `gunicorn` 21.2.0 | **done** → 22.0.0 (`3346b51`) | request-smuggling rows cleared; Caddy path passed |
| `PyPDF2` 3.0.1 | **done** → `pypdf` 6.14.2 (`5743b82`) | 12 production imports plus tests migrated; parity/adversarial and production gates passed |
