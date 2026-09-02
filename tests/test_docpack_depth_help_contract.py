"""The published help is the spec for the Doc Pack depth choice.

The option was called "Top level only" while it meant "the root and the parts
directly under it", and the troubleshooting page said the opposite - that it
"excludes children". Renaming it fixes the label in one place and leaves three
others to drift, so these tests read the help file itself and hold every
surface that offers the choice to the wording it promises.
"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WALKTHROUGH = REPO_ROOT / "docs" / "help" / "01_web_ui_walkthrough.md"
TROUBLESHOOTING = REPO_ROOT / "docs" / "help" / "07_troubleshooting.md"
PART_DETAIL = REPO_ROOT / "frontend" / "src" / "pages" / "PartDetailPage.tsx"
JOBS_FORM = REPO_ROOT / "app" / "templates" / "admin" / "jobs_form.html"
ORDERS_FORM = REPO_ROOT / "app" / "templates" / "admin" / "orders_form.html"

FIRST_LEVEL_LABEL = "This part + its children"
FULL_LABEL = "Full BOM (all levels)"


def _doc_pack_help() -> str:
    body = WALKTHROUGH.read_text(encoding="utf-8")
    start = body.index("## Doc Packs")
    return body[start : body.index("\n## ", start + 1)]


def test_help_names_the_two_depth_choices_the_ui_offers():
    text = _doc_pack_help()
    assert FIRST_LEVEL_LABEL.lower() in text.lower()
    assert "full bom (all levels)" in text.lower()
    assert "top level only" not in text.lower(), (
        "the old label is still in the help; a user cannot find that control"
    )


def test_every_screen_offering_the_choice_uses_the_documented_wording():
    """Part detail, the job form and the order form all build doc packs."""

    for path in (PART_DETAIL, JOBS_FORM, ORDERS_FORM):
        source = path.read_text(encoding="utf-8")
        assert FIRST_LEVEL_LABEL in source, f"{path.name} still uses the old depth label"
        assert FULL_LABEL in source, f"{path.name} does not name the full-BOM choice"
        assert "Top level only" not in source
        assert "Top Level only" not in source


def test_help_promises_the_scope_covers_the_root_and_stops_below_its_children():
    """The two claims the fix had to make true, stated in the help."""

    text = _doc_pack_help().lower()
    assert "directly under it" in text, (
        "the help must say the immediate components are included"
    )
    assert "sub-assembly appears as a line item" in text, (
        "the help must say a sub-assembly is listed but not opened up"
    )


def test_help_lists_the_outputs_the_depth_choice_governs():
    """Each output named here has a test in test_docpack_depth_first_level."""

    text = _doc_pack_help().lower()
    for output in ("files", "excel bom", "binder", "visual summary", "hardware summary"):
        assert output in text, f"the help does not say the depth applies to the {output}"


def test_troubleshooting_no_longer_claims_the_option_excludes_children():
    text = TROUBLESHOOTING.read_text(encoding="utf-8").lower()
    assert "top level only* excludes children" not in text
    assert FIRST_LEVEL_LABEL.lower() in text
