# CSP `unsafe-inline` burn-down

Blocker: **SEC-CSP-01** · Phase 1A residual → Phase 2

Written 2026-08-03. Mechanism landed; the template migration itself is **not
done** and is deliberately left as sequenced work.

## Position

`Content-Security-Policy` still ships `'unsafe-inline'` in `script-src` and
`style-src`, so the CSP does not currently stop injected inline script. Phase 1A
closed the stored-XSS hole that made that dangerous, but CSP is the defence in
depth and it is presently soft.

The blocker cannot be closed by editing the header, because 12 templates and 33
inline event handlers depend on inline execution. Flipping
`TINYMRP_CSP_ALLOW_INLINE=false` today breaks the admin UI.

## What this change adds

Three things that make the migration incremental and measurable, without
changing the enforced policy:

### 1. A per-response nonce

`app/__init__.py` generates a CSPRNG nonce per request and exposes it to
templates as `csp_nonce()`. A migrated template writes:

```html
<script nonce="{{ csp_nonce() }}">
```

A nonced script keeps working *after* `'unsafe-inline'` is dropped, so templates
can be migrated one at a time and verified individually.

### 2. The nonce is withheld while inline is allowed

This is the subtle part, and it is enforced by a test.

Browsers **ignore `'unsafe-inline'` whenever a nonce is present** in the same
directive. So emitting both would instantly break every not-yet-migrated
template — the exact big-bang this design exists to avoid.

The nonce is therefore only emitted once `TINYMRP_CSP_ALLOW_INLINE=false`.
During migration, add `nonce="{{ csp_nonce() }}"` to templates freely: the
attribute is inert while inline is still allowed, and becomes load-bearing the
moment inline is switched off.

### 3. A report-only probe

Set `TINYMRP_CSP_REPORT_ONLY_STRICT=true` to emit
`Content-Security-Policy-Report-Only` carrying the **stricter** policy (no
`'unsafe-inline'`, nonce present) alongside the normal enforced header.
Browsers then report every violation that *would* occur without blocking
anything. Add `TINYMRP_CSP_REPORT_URI` to collect them.

This is how to size the remaining work with evidence instead of grep.

## Current inline surface

Measured 2026-08-03:

| | Count |
| --- | --- |
| Templates with an inline `<script>` block | 12 |
| Inline event handler attributes (`onclick=` etc.) | 33 |

Templates with inline `<script>`, heaviest first:

```
3  app/templates/admin/orders_form.html
3  app/templates/admin/jobs_form.html
2  app/templates/admin/suppliers_form.html
2  app/templates/admin/customers_form.html
1  app/templates/ui/react_shell.html
1  app/templates/tools/excel_compile.html
1  app/templates/security/base.html
1  app/templates/home.html
1  app/templates/help/index.html
1  app/templates/admin/settings.html
1  app/templates/admin/rescan_files.html
1  app/templates/admin/purge_parts.html
```

Note the 33 inline handlers are a **separate problem**: a nonce does not
authorise `onclick=`. Those must become `addEventListener` calls inside a
nonced or external script. `jobs_form.html` alone has several
(`onclick="setCheckboxGroup(...)"`).

## Suggested sequence

1. Turn on the report-only probe in a non-production environment and exercise
   the admin UI. Collect the real violation set.
2. Add `nonce="{{ csp_nonce() }}"` to each inline `<script>`. Inert until step 4,
   so this can land in small commits.
3. Convert the 33 inline handlers to `addEventListener` inside those nonced
   blocks. This is the actual work and the part that needs UI regression
   testing.
4. Flip `TINYMRP_CSP_ALLOW_INLINE=false` in one environment, verify, then make
   it the default.
5. Drop `'unsafe-inline'` from `style-src` too — check the inline `style="..."`
   attributes separately, as those need `'unsafe-inline'` in *style-src*
   specifically and a nonce does not cover them.

Steps 2–3 are the bulk. Step 5 is easy to forget: script and style are
independent directives.

## Verification

`tests/test_csp_policy.py` (9 tests) pins all of the above — CSP previously had
no direct coverage at all. Notably it asserts the nonce is *absent* while inline
is allowed; that test was confirmed to fail against a deliberately injected
regression that emitted both.

Full suite after this change: **613 passed, 1 skipped**.

## Not done

- No template was migrated. The enforced policy is byte-identical to before.
- `TINYMRP_CSP_REPORT_ONLY_STRICT` defaults to off, so nothing changes for
  existing deployments unless it is explicitly enabled.
- No `report-uri` endpoint is implemented in the app; the setting expects an
  external collector.
