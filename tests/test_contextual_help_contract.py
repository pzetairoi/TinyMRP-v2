"""UI-only contracts for the central Help library and contextual links."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HELP_DIR = REPO_ROOT / "app" / "static" / "help"


def _toc() -> dict:
    return json.loads((HELP_DIR / "help_toc.json").read_text(encoding="utf-8"))


def _help_map() -> dict:
    return json.loads((HELP_DIR / "context_help.json").read_text(encoding="utf-8"))


def test_every_canonical_document_is_in_the_help_library_once():
    all_docs = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "docs").rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    }
    developer_history = {
        source
        for source in all_docs
        if source.startswith("docs/planning/")
        or source in {
            "docs/PRODUCTION_HARDENING_BASELINE.md",
            "docs/UPDATING_PRODUCTION.md",
        }
    }
    developer_history.add("CHANGELOG.md")
    expected = (all_docs - developer_history) | {"README.md", "SECURITY.md"}

    toc = _toc()
    published = [
        chapter["source"]
        for group in toc["items"]
        for chapter in group["chapters"]
    ]

    assert toc["schema_version"] == 2
    assert toc["source_count"] == len(expected)
    assert set(published) == expected
    assert len(set(published)) == toc["source_count"]
    assert developer_history.isdisjoint(published), "developer history leaked into end-user Help"


def test_help_library_has_one_default_and_hides_developer_history():
    groups = _toc()["items"]
    assert [group["id"] for group in groups if group.get("default")] == ["user-guide"]
    assert "history" not in {group["id"] for group in groups}


def test_contextual_help_targets_exist_in_the_generated_help():
    help_html = (HELP_DIR / "help.html").read_text(encoding="utf-8")
    target_ids = set(re.findall(r'\bid="([^"]+)"', help_html))
    mapping = _help_map()
    targets = [mapping["default"]["target"]] + [rule["target"] for rule in mapping["rules"]]
    assert not (set(targets) - target_ids)


def test_generated_document_links_resolve_inside_the_library():
    help_html = (HELP_DIR / "help.html").read_text(encoding="utf-8")
    target_ids = set(re.findall(r'\bid="([^"]+)"', help_html))
    in_page_links = set(re.findall(r'href="#([^"]+)"', help_html))
    relative_source_links = re.findall(
        r'href="(?!https?://|/|#|mailto:)([^"]+\.(?:md|txt)(?:#[^"]*)?)"',
        help_html,
    )

    assert not (in_page_links - target_ids)
    assert not relative_source_links


def test_every_authenticated_ui_area_has_a_contextual_help_rule():
    """Representative paths include list, detail, create and settings views."""

    representative_paths = (
        "/app",
        "/ui/dashboard",
        "/ui/parts",
        "/ui/part/CV03-TR-A01",
        "/ui/bom/CV03-TR-A01",
        "/ui/upload-pack",
        "/ui/addin/tokens",
        "/ui/admin/addin",
        "/ui/admin/fields",
        "/tools/",
        "/tools/excelcompile",
        "/admin/",
        "/admin/jobs/123/edit",
        "/admin/orders/new",
        "/admin/customers/123",
        "/admin/suppliers/new",
        "/admin/users/123/edit",
        "/admin/roles/new",
        "/admin/settings",
        "/admin/backups",
        "/admin/audit/",
        "/admin/metrics",
        "/admin/rescan-files",
        "/admin/purge-parts",
    )
    rules = _help_map()["rules"]

    def covered(path: str) -> bool:
        return any(
            path == rule["path"] if rule["match"] == "exact" else path.startswith(rule["path"])
            for rule in rules
        )

    assert not [path for path in representative_paths if not covered(path)]


def test_shared_ui_layout_exposes_help_without_backend_changes():
    base = (REPO_ROOT / "app" / "templates" / "security" / "base.html").read_text(encoding="utf-8")
    script = (REPO_ROOT / "app" / "static" / "js" / "context-help.js").read_text(encoding="utf-8")

    assert 'id="contextHelpLink"' in base
    assert "help/context_help.json" in base
    assert "js/context-help.js" in base
    assert "Documentation library" in base
    assert "button[aria-label]" in script
