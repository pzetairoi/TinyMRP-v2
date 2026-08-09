# CONTRIBUTING_HELP

This file describes how to write and maintain the help content in `docs/help/`.

## Tone and audience

- Write for non-IT users.
- Use clear, short sentences.
- Define terms before using them.

## Structure rules

- Use `#` for the main section title of a file.
- Use `##` for sections and `###` for subsections.
- Keep headings short and consistent.
- Include "Where to find it", "What you can do", "Step-by-step", and "Troubleshooting" for UI pages.

## Formatting rules

- Use numbered steps for procedures.
- Use bold callouts like **Tip:** or **Common mistake:**.
- Avoid long paragraphs.

## Auto-generated sections

- Do not manually edit content inside `{{AUTO_*}}` placeholders.
- Update the generator instead if the format is wrong.

## Regenerate the help page

1) Run `flask help build`.
2) Commit `app/static/help/help.html` and `app/static/help/help_toc.json`.

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

