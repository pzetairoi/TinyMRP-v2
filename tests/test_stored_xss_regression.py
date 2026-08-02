"""Stored-XSS regression tests for the job and order line editors (Phase 1A).

Both forms render BOM/order rows client-side from values that originate in the
database (part numbers, descriptions, revisions, UoM, notes and thumbnail URLs
returned by /api/part_detail). They previously built each row with a template
literal assigned to ``tr.innerHTML``, so a part whose description contained
markup executed script in every job or order referencing it.

The rows are now built with createElement + textContent/property assignment.
These tests pin that invariant at the source level: they fail if anyone
reintroduces HTML-string construction of row content, which is the mistake that
caused the vulnerability rather than any single payload.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates" / "admin"

FORMS = {
    "jobs_form.html": "renderBomTable",
    "orders_form.html": "renderOrderTable",
}

# Harmless but unambiguously hostile strings. If any of these can reach an HTML
# parser through the row renderers, the row values are not being escaped.
HOSTILE_VALUES = [
    '<img src=x onerror="window.__xss=1">',
    "<script>window.__xss=1</script>",
    '"><svg onload="window.__xss=1">',
    "javascript:window.__xss=1",
    "'\"><b>bold</b>",
]


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _render_body(source: str, func: str) -> str:
    """Return the body of the row-rendering function."""
    start = source.index(f"function {func}(")
    # Walk braces from the function's opening brace to its matching close.
    brace = source.index("{", start)
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[brace : i + 1]
    raise AssertionError(f"unbalanced braces in {func}")


@pytest.mark.parametrize("name,func", FORMS.items())
def test_row_renderer_does_not_assign_html_strings(name, func):
    """The renderer must not write markup built from row values."""
    body = _render_body(_read(name), func)

    # The only tolerated innerHTML use is clearing the table with a constant.
    for match in re.finditer(r"\.innerHTML\s*=\s*(.+)", body):
        value = match.group(1).strip()
        assert value.startswith(("''", '""')), (
            f"{name}:{func} assigns a non-constant value to innerHTML: {value!r}. "
            "Row content must be set with textContent or element properties."
        )

    for sink in (".insertAdjacentHTML", ".outerHTML", "document.write"):
        assert sink not in body, f"{name}:{func} uses unsafe sink {sink}"


@pytest.mark.parametrize("name,func", FORMS.items())
def test_row_values_are_written_as_text_not_markup(name, func):
    """Untrusted row fields must reach the DOM via textContent/value only."""
    body = _render_body(_read(name), func)

    # No template literal in the renderer may contain a tag, which is how the
    # original vulnerable code embedded row values.
    for literal in re.findall(r"`[^`]*`", body):
        assert "<" not in literal, (
            f"{name}:{func} builds markup in a template literal: {literal!r}. "
            "Build elements with createElement instead."
        )

    assert "textContent" in body, f"{name}:{func} should set text via textContent"


@pytest.mark.parametrize("name", FORMS)
def test_thumbnail_urls_are_scheme_checked(name):
    """A stored thumbnail URL must not be able to carry a script scheme."""
    source = _read(name)
    assert "function safeImageSrc(" in source, f"{name} lost the image-URL guard"

    body = _render_body(source, "safeImageSrc")
    # Anything with a scheme must be http(s) to be used verbatim.
    assert "https?:" in body, f"{name}: safeImageSrc must restrict URL schemes"
    assert "fallbackLogo" in body, f"{name}: safeImageSrc must have a safe fallback"


@pytest.mark.parametrize("name,func", FORMS.items())
@pytest.mark.parametrize("payload", HOSTILE_VALUES)
def test_hostile_values_have_no_interpolation_site(name, func, payload):
    """There is no HTML-string site where a hostile row value could land.

    This is the behavioural claim the payloads stand in for: with row content
    built exclusively through createElement, none of these strings can be
    parsed as markup regardless of what is stored in the database.
    """
    body = _render_body(_read(name), func)

    # Row fields must never appear inside a template literal (the only way a
    # string in this renderer becomes markup).
    for field in ("row.pn", "row.desc", "row.rev", "row.uom", "row.note", "row.thumb"):
        for literal in re.findall(r"`[^`]*`", body):
            if field in literal:
                # Permitted only for URL building, which is encodeURIComponent'd
                # and never assigned as HTML.
                assert "encodeURIComponent" in literal, (
                    f"{name}:{func} interpolates {field} into a literal that is "
                    f"not URL-encoded: {literal!r} (payload example: {payload!r})"
                )


def test_no_new_unsafe_sinks_in_admin_templates():
    """Guard the wider template tree against reintroduced innerHTML sinks."""
    offenders = []
    for path in sorted(TEMPLATES.glob("*.html")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ".innerHTML" not in line:
                continue
            value = line.split(".innerHTML", 1)[1]
            if "=" not in value:
                continue
            assigned = value.split("=", 1)[1].strip()
            if not assigned.startswith(("''", '""')):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")

    assert not offenders, "unsafe innerHTML assignments found:\n" + "\n".join(offenders)
