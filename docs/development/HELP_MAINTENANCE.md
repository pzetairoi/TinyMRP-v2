# Maintaining Help and documentation

Repository documents are the source of truth. The Help build publishes only
approved user and operator sources; developer notes and project history stay in
the repository.

## Writing user Help

- Put day-to-day application guidance in `docs/help/`.
- Use one `#` title, `##` sections and short task-focused headings.
- Explain where to find a control, what it does and what can prevent access.
- Use numbered steps for procedures and captions for screenshots.
- Do not place implementation plans, API inventories, test notes or remediation
  records in `docs/help/`.

## Published sections

- `docs/help/` user guides, except the server-install pointer: **User guide**.
- `docs/deployment/`, except local development, the production-update entry
  point, and the server-install pointer: **Installation & operations**.
- `docs/commercial/PRODUCT_SCOPE.md`: **Product information**.

Everything under `docs/development/`, `docs/history/` and `docs/security/`, the
local-development guide, root `README.md`, `SECURITY.md` and `CHANGELOG.md` is
repository-only.

## Generated content and contextual links

Do not edit `{{AUTO_*}}` output by hand. Update `tools/build_help.py` when a
generated table is wrong. Route-to-section targets for the compact `?` link live
in `app/static/help/context_help.json`; each target must remain a stable
user-guide anchor.

## Build and verify

1. Edit the canonical source.
2. Run `python tools/build_help.py`.
3. Run
   `pytest -q tests/test_help_page.py tests/test_documentation_hygiene.py tests/test_contextual_help_contract.py`.
4. Check the default User guide, each published section, search, deep links and
   the responsive contents drawer.
5. Follow the contextual `?` link from representative application pages.
6. Commit the generated `app/static/help/help.html` and
   `app/static/help/help_toc.json` with the source changes.

## Screenshots

Images live in `app/static/help/img/` and are captured by Playwright scripts in
`frontend/tools/`:

- `capture-help-shots.mjs` — the static surfaces (inventory, import, roles, part
  detail, portal).
- `capture-job-ordering-shots.mjs` — Workflow B, which is a stateful sequence:
  it raises an order from a job, submits it and photographs coverage moving.
  Run `seed-help-job.py` first to reset the worked example.

**Capture against a disposable instance, never the development one.** Its
database holds real part numbers. Stand up an isolated instance with its own
database, deliverables root and port, then seed it:

```bash
ENV_FILE=<instance env> python -m flask --app run.py user seed-roles
ENV_FILE=<instance env> python -m flask --app run.py demo install --domain demo.com
ENV_FILE=<instance env> python frontend/tools/seed-help-job.py
```

`demo install` prints the generated passwords once; the capture scripts read
them from `HELP_*_EMAIL` / `HELP_*_PASSWORD` environment variables. Each script
documents its own variables in its header comment. Tear the instance down with
`flask demo remove --domain demo.com --disable` and drop its database.
