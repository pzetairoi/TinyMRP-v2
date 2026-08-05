"""No inline event handlers in templates (SEC-CSP-01, Phase 1A residual).

Inline ``on*=`` attributes cannot execute under a Content-Security-Policy
without ``'unsafe-inline'``, and a nonce does NOT authorise them -- a nonce
only covers ``<script>`` blocks. They were therefore the hard blocker on
tightening script-src, not the inline ``<script>`` blocks themselves.

All 33 were converted to ``data-act`` attributes handled by delegated
listeners (``app/static/js/admin-actions.js`` for the shared ones). This test
stops them coming back, because a single reintroduced ``onclick=`` silently
re-blocks the whole burn-down.
"""

from __future__ import annotations

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"

# Matches on<event>= inside a tag. Deliberately broad: any inline handler is a
# blocker, not just the ones currently in use.
INLINE_HANDLER = re.compile(r"\son[a-z]+\s*=\s*[\"']", re.IGNORECASE)


def _offenders() -> list[str]:
    hits: list[str] = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if INLINE_HANDLER.search(line):
                rel = path.relative_to(TEMPLATES)
                hits.append(f"{rel}:{lineno}: {line.strip()[:100]}")
    return hits


def test_no_inline_event_handlers_in_templates():
    offenders = _offenders()
    assert not offenders, (
        "Inline event handlers block the CSP burn-down (SEC-CSP-01). Use a "
        "data-act attribute plus a delegated listener instead -- see "
        "app/static/js/admin-actions.js:\n" + "\n".join(offenders)
    )


def test_shared_delegated_handler_script_exists():
    """The templates rely on this file; losing it silently breaks every button."""
    script = TEMPLATES.parents[0] / "static" / "js" / "admin-actions.js"
    assert script.is_file(), "app/static/js/admin-actions.js is missing"

    source = script.read_text(encoding="utf-8")
    for action in ("checkgroup", "check-selector", "confirm-submit"):
        assert f"'{action}'" in source, f"delegated action {action} is not handled"


def test_base_template_loads_the_shared_script():
    base = TEMPLATES / "security" / "base.html"
    assert "js/admin-actions.js" in base.read_text(encoding="utf-8"), (
        "base.html must load the delegated handler script, or data-act buttons "
        "do nothing on pages that extend it"
    )
