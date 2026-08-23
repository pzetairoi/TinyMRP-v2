# CONTRIBUTING_HELP

This file describes how to write and maintain the Help UI. Repository
documentation remains the single source of truth: the build publishes the
original files into one searchable Help library instead of maintaining a
second copy.

## Tone and audience

- Write for non-IT users.
- Use clear, short sentences.
- Define terms before using them.

## Structure rules

- Use `#` for the main section title of a file.
- Use `##` for sections and `###` for subsections.
- Keep headings short and consistent.
- Include "Where to find it", "What you can do", "Step-by-step", and "Troubleshooting" for UI pages.

## Library sections

The Help page opens on **User guide**, which is built from the operator-facing
files in `docs/help/`. Other repository sources are available from the section
selector and **Documentation library** account-menu link:

- `docs/deployment/` and the server-install pointer: **Installation & operations**.
- `SECURITY.md` and `docs/security/`: **Security & governance**.
- `docs/commercial/`: **Product & support**.
- `README.md`, field/testing references and generated reference material:
  **Engineering & reference**.
- `CHANGELOG.md`, production snapshots and `docs/planning/` remain
  **developer-only history and evidence** in the repository. They are not
  published in the end-user Help UI.

The builder automatically includes every current `.md` source under `docs/`;
the coverage test fails if the generated table of contents drifts. Historical
sources remain checked separately by the documentation-hygiene tests.

## Contextual help

Every authenticated view inherits the compact `?` help link from
`app/templates/security/base.html`. Route-to-section targets and hover labels
live in `app/static/help/context_help.json`; keep those targets on stable
operator-help anchors. `app/static/js/context-help.js` applies the mapping and
adds native hover descriptions to icon controls that already have accessible
names. Prefer visible button text for ordinary actions and explicit
`aria-label` plus `title` for icon-only controls.

## Formatting rules

- Use numbered steps for procedures.
- Use bold callouts like **Tip:** or **Common mistake:**.
- Avoid long paragraphs.

## Auto-generated sections

- Do not manually edit content inside `{{AUTO_*}}` placeholders.
- Update the generator instead if the format is wrong.

## Regenerate the help page

1. Edit the applicable canonical source file; do not copy its prose elsewhere.
2. Run `flask help build` (or `python tools/build_help.py`).
3. Run `pytest -q tests/test_help_page.py tests/test_documentation_hygiene.py tests/test_contextual_help_contract.py`.
4. Check `/help` in the default User guide scope, each library section, search,
   a deep link, and a narrow/mobile viewport.
5. From representative UI pages, follow the floating `?` link and confirm it
   opens the applicable section.
6. Commit `app/static/help/help.html` and `app/static/help/help_toc.json` with
   the source and UI changes.

## Refresh screenshots

The capture uses the real dev UI, Playwright Chromium and the reserved
permission-test accounts. Before running it:

1. Start a dev server against the intended localhost Mongo database.
2. Configure its deliverables root so Part Detail and drawing markup files are
   actually served. For a clean environment, install the canonical fixture
   with `python tools/install_sample_dataset.py --destination <root>`.
3. Seed or refresh the reserved permission-test environment and place its
   administrator and customer credentials in `HELP_ADMIN_EMAIL`,
   `HELP_ADMIN_PASSWORD`, `HELP_CUSTOMER_EMAIL` and `HELP_CUSTOMER_PASSWORD`.
4. Run `python tools/capture_help_shots.py --base http://localhost:5000`.

The script overwrites the PNG files in `app/static/help/img/`. It creates the
upload-pack example entirely in memory and presses **Preview changes** only; it
never applies that import. Inspect every changed image before rebuilding help.
Every part-bearing capture must use `CV03-TR-A01` revision A or a child from its
checked-in BOM; do not substitute unrelated engineering data.

