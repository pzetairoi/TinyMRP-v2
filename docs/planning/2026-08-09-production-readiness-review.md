# Production readiness review — 2026-08-09

Author: Claude (this session). Scope: full read of `docs/planning/hardeningplan.txt`,
`docs/planning/posthardeningplan.txt`, `docs/planning/optimizationplan.txt`,
`docs/planning/postoptimizationplan.txt` and `docs/planning/productionmaturityplan.txt`, cross-checked
directly against the current code (not just against what the plans claim).
Excludes Lane F (documentation/commercial, Codex's in-flight work) and the
Nextcloud E1/N11 backlog item — both explicitly out of scope for this review,
not overlooked.

**How to use this file**: it is a snapshot, not a plan. If you are picking this
up later — Claude or Codex — re-verify anything you're about to act on rather
than trusting a line here; code moves, this file does not. The numbered
recommendations at the bottom are the actionable part; everything above is the
evidence for why they're on the list.

---

## Verdict

TinyMRP's security core is solid and **verified**, not just declared — session
cookies, CSRF, CSP, rate limiting, secrets handling, path-traversal
containment, RBAC and supply-chain scanning all checked directly against the
running code, not taken on the plan documents' word. Performance on the
critical paths is backed by real before/after measurements across three plan
generations, including two N+1 defects found and fixed *this session*
(`_flatten_bom`'s memoisation re-verified; `arena_export.py`'s walk() found
unfixed and corrected). What's missing isn't a security hole — it's **field
evidence**: an actual restore of the current backup format has never been
demonstrated, the single largest and most-used page in the app
(`PartDetailPage.tsx`, 4069 lines) has zero automated test coverage, and
accessibility checking exists on exactly one screen (login) out of nine. None
of that blocks a careful internal professional deployment. All of it should
close before calling this finished.

---

## Security — solid, verified directly against code

- **One auth model, no bypass.** `compat` mode and the legacy admin-bypass
  role were deleted outright (A2/A3, 2026-08-09), not disabled. Verified: no
  code path re-enables either.
- **Mongo authentication live fleet-wide**, verified positively — an
  unauthenticated request to `mecs` is refused. (This resolves an internal
  contradiction found in the now-archived `docs/planning/postoptimizationplan.txt`, which
  had two sections disagreeing on whether `mecs` was covered; the current
  state is unambiguous and later than that contradiction.)
- **Session/CSRF**: `SESSION_COOKIE_HTTPONLY=True`, `SAMESITE=Strict` in
  production, `SECURE=True` (`app/__init__.py:181-234`). Session CSRF checks
  the request's Origin/Referer and fails closed.
- **Security headers**: `X-Content-Type-Options`, `Strict-Transport-Security`,
  `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`
  (`app/__init__.py:566-576`).
- **CSP verified in a real browser**, not just configured: `script-src` is
  strict with a per-request nonce, no `unsafe-inline`. `style-src` keeps
  `unsafe-inline` as a documented, deliberate, low-risk decision (it can't
  execute code) — not unfinished work. This is task A1 in
  `docs/planning/productionmaturityplan.txt`, which is the current name for the older
  docs' `SEC-CSP-01` / "CSP browser check never done" — that flag is
  resolved, closed with actual browser evidence (three real pages, zero
  script-src violations).
- **Rate limiting on Redis, shared across gunicorn workers.** Has a real
  history: an ordering bug silently made per-endpoint limits a no-op for
  weeks (`docs/planning/posthardeningplan.txt`), found only by starting it on
  real hardware. Fixed and verified end-to-end against a real Redis.
- **Secrets never self-generated.** `SECRET_KEY`/`SECURITY_PASSWORD_SALT` are
  required; the app refuses to start without them
  (`app/services/runtime_secrets.py:125`).
- **Path-traversal containment** verified in `app/services/file_security.py`
  (`_inside()`, `_validate_candidate`).
- **RBAC**: one canonical permission registry
  (`app/services/permissions.py:13-114`), no bypass role left anywhere.
- **Supply chain**: bandit, pip-audit, npm audit, gitleaks all wired in CI;
  `requirements.lock` hash-verified; Trivy HIGH/CRITICAL gate + SBOM in
  `release-image.yml` (an older audit thought this was `continue-on-error`
  and non-blocking — that was wrong, and was corrected in
  `docs/planning/posthardeningplan.txt` itself; current code confirms it
  blocks).
- **Three real security defects found by testing, not code review, and
  verified fixed in current code**:
  - Bulk user deletion used to fail *open* if the admin-role check threw —
    now explicitly fails closed (`app/views/admin.py:544-558`, comment
    documents the old bug).
  - Two authorization mechanisms disagreeing on "where-used" visibility
    (potential leak or false-deny) — unified onto one (`authorised_get`,
    `app/views/ui.py:68-80`, comment documents the old inconsistency).
  - Backups were silently empty for weeks after Mongo auth was enabled
    (`mongodump` refused, wrote a 23-byte header, exited 0) — found before a
    rebuild that would have destroyed real production data; retention and
    cadence now bounded by policy (A4, this session).

### Real remaining gap — not a hole, a missing proof

- **A4's own stated DONE WHEN** ("a restore from the new [split-cadence]
  layout has been proven on a disposable instance") is not confirmed
  anywhere in the closure log. What *is* confirmed: the daily/weekly jobs run,
  produce correctly-sized non-empty archives, and existing full backups were
  "verified still present" after a prune — which is a materially weaker
  check than an actual restore. This is the single rule repeated verbatim
  across all the historical plans ("a backup is not a backup until it has
  been restored") and it has already cost this project real data exposure
  twice. **Recommendation #1 below.**

### Minor documentation hygiene, not a risk

- `docs/PRODUCTION_HARDENING_BASELINE.md` is a frozen snapshot from
  2026-08-07 (one incidental touch since). Its blocker table still shows
  several items as "Open" that are actually closed in the current
  `docs/planning/productionmaturityplan.txt` (e.g. `SEC-CSP-01`, `OPS-DBAUTH-01`,
  `QA-FE-01`). Treat `docs/planning/productionmaturityplan.txt` as authoritative for
  current status; this file is historical evidence, same as the newly-moved
  `docs/planning/*.txt` files.

---

## Performance — measured, not assumed

- Real, named before/after numbers across the plan history:
  `docpacks/options` 9665→52 ops, `bom_tree` 64→21 ops, `part_detail`
  52→29 ops, idle Mongo CPU 39%→0.5%.
- `_flatten_bom` re-measured this session (D1): the existing memoisation
  already fixed the multiplicative revisit cost it was built for — 1.00
  queries per distinct part, down from a documented ~4.93/part pre-fix.
  Closed without code, per the task's own rule.
- **A real, previously-unfixed N+1 found and fixed this session (D2)**: two
  `walk()` functions in `app/services/arena_export.py` called
  `_child_links()` fresh on every visit with no cache at all — the same
  defect `_flatten_bom` had, never applied here. A/B'd against the pre-fix
  committed source: overhead **compounded with depth** on the unfixed code
  (1.48x queries/part at 3 layers → 3.07x at 5), flat 1.00x on the fixed
  version regardless of depth. Fixed while preserving a real correctness
  constraint (Arena's BOM export needs one CSV row per occurrence-path, so
  only the constant-per-part lookups were memoised, not the walk itself).
  Two regression tests added.
- `bom_flat` (the endpoint that used to cause 502 timeouts on large
  assemblies via a per-part thumbnail storage scan) verified fixed — the
  scan is now batched into one pass per request
  (`app/views/bom_tree.py:636-643`).

### Minor remaining item

- Main JS bundle is still 984 KB (274 KB gzipped) and triggers Vite's
  oversized-chunk warning, even after B1's 27% cut. Not urgent for an
  internal engineering tool; worth another code-splitting pass eventually.

---

## UI / UX — the area with the most real, named debt

- Browser suite (Playwright + axe) **actually runs in CI now**, against a
  freshly seeded real instance — this session found and fixed the case where
  it was silently skipping on every PR (gated on an env var nothing set) and
  still reporting green. 7 tests now execute for real
  (`frontend/e2e/critical-path.spec.ts`).
- 8 of 9 frontend pages have a dedicated test file.

### Real gaps, worth naming plainly

- **`PartDetailPage.tsx` (4069 lines) has zero page-level test coverage.**
  It is the single largest, most complex, most-used page in the application
  — the one a regression is least likely to be caught in before a real user
  hits it. This is the most significant single item in this whole review.
- **Automated accessibility checking (axe) exists on exactly one screen:
  login.** None of the actual working surfaces — parts list, part detail,
  BOM, admin — have any automated a11y check, despite WCAG 2.2 AA being a
  named target in the original hardening roadmap.
- Silent-exception triage was risk-ranked, not count-chased: 17 of 276
  handlers changed after confirming none of the untouched 259 could produce
  a wrong answer that looks right (89 are PDF/format parsing where
  swallowing is correct; the rest are best-effort UI decoration or
  already-logged accessor failures). Documented reasoning in
  `docs/planning/productionmaturityplan.txt`'s B3 closure — don't re-open this as a
  counting exercise without a specific regression to justify it.

---

## Recommendations, in priority order

1. **Prove a real restore.** Take the current (post-A4) backup format,
   restore it on a disposable instance using the fleet's actual
   `restore-instance.sh`, and confirm data integrity. This is the one rule
   every plan generation states explicitly and none has proven for the
   *current* backup layout. Do this before trusting it with a real
   customer's only copy of their data.
2. **Write tests for `PartDetailPage.tsx`.** It's the highest-traffic,
   highest-complexity page with the least safety net. Even a first pass
   covering load/error states and the BOM section (mirroring the pattern
   already used for the other 8 pages) would materially reduce risk.
3. **Extend axe coverage past the login page** to parts list, part detail,
   and at least one admin screen, if "professional environment" needs to
   include accessibility compliance for procurement or actual users with
   accessibility needs.
4. **If this is going to an external/paying customer, not just internal
   use**: F2 (legal/commercial review) is explicitly gated behind
   owner/counsel, not engineering, and is still open. Don't let engineering
   completeness stand in for that.
5. **Decide 2FA deliberately.** It exists, works, defaults off
   (`SECURITY_TWO_FACTOR_ENABLED`). Fine for a small office; make it an
   explicit choice for the target deployment rather than an unexamined
   default.
6. Bundle size (984 KB / 274 KB gz) — low priority, revisit if load time
   ever becomes a real complaint.
7. Either update `docs/PRODUCTION_HARDENING_BASELINE.md`'s blocker table to
   match current reality or add a banner marking it historical, so nobody
   re-opens an already-closed item by trusting it over
   `docs/planning/productionmaturityplan.txt`.

None of the above reads as "unsafe for production" on its own. Together, #1
and #2 are the two I'd actually block a real customer rollout on until
closed — everything else is real, worth doing, and not urgent.
