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

