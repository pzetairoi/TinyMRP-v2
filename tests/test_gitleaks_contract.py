"""Regression contracts for effective repository secret scanning."""

from __future__ import annotations

from pathlib import Path
import re
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]


def _config() -> dict:
    with (REPO_ROOT / ".gitleaks.toml").open("rb") as stream:
        return tomllib.load(stream)


def _allowlist_paths(config: dict) -> list[str]:
    paths: list[str] = []

    def visit(value: object, *, inside_allowlist: bool = False) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_is_allowlist = inside_allowlist or key in {"allowlist", "allowlists"}
                if child_is_allowlist and key == "paths" and isinstance(child, list):
                    paths.extend(item for item in child if isinstance(item, str))
                visit(child, inside_allowlist=child_is_allowlist)
        elif isinstance(value, list):
            for child in value:
                visit(child, inside_allowlist=inside_allowlist)

    visit(config)
    return paths


def test_gitleaks_config_extends_the_builtin_detection_rules() -> None:
    config = _config()

    assert config.get("extend", {}).get("useDefault") is True


def test_gitleaks_allowlist_is_limited_to_generated_or_vendored_files() -> None:
    config = _config()
    patterns = _allowlist_paths(config)

    assert "allowlist" not in config  # Deprecated singular global table must not return.
    assert set(patterns) == {
        r"^frontend/node_modules/",
        r"^frontend/dist/",
        r"^app/static/parts-ui/assets/.*\.(?:eot|ttf|woff2?)$",
    }

    excluded_generated_files = (
        "frontend/node_modules/example/index.js",
        "frontend/dist/index.js",
        "app/static/parts-ui/assets/InterVariable.woff2",
    )
    for path in excluded_generated_files:
        assert any(re.search(pattern, path) for pattern in patterns)


def test_gitleaks_allowlist_cannot_hide_human_authored_or_fixture_paths() -> None:
    patterns = _allowlist_paths(_config())

    paths_that_must_be_scanned = (
        "docs/operator-runbook.md",
        "testfiles/bom/customer-upload.zip",
        "app/static/admin-access.js",
        "app/static/help/help.html",
        "app/static/parts-ui/assets/index.js",
        "frontend/src/main.tsx",
    )
    for path in paths_that_must_be_scanned:
        assert not any(re.search(pattern, path) for pattern in patterns)
