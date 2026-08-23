"""The documentation must stay navigable, factual and singly-sourced.

Prose rots differently from code: nothing fails when a README describes a flag
that was deleted, or when a second copy of an install guide drifts from the
first. A colleague following the wrong copy loses an afternoon, which is what
prompted these checks.

Every assertion here corresponds to something that was actually wrong.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _docs() -> list[Path]:
    out = []
    for pattern in ("*.md", "docs/**/*.md", "deploy/**/*.md", "frontend/*.md",
                    "solidworks-addin/*.md"):
        out.extend(REPO_ROOT.glob(pattern))
    skip = ("node_modules", ".venv", "sample_data", "/bin/", "/obj/")
    return sorted({p for p in out if p.is_file() and not any(s in p.as_posix() for s in skip)})


def _slug(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.strip().lower(), flags=re.UNICODE)
    return text.replace(" ", "-")


# docs/help/ is compiled into one page and served by Flask, so its image paths
# are runtime URLs and its anchors point across chapters. Those are checked by
# tests/test_help_page.py against the built artefact instead.
_COMPILED_INTO_ONE_PAGE = "docs/help/"


def test_every_relative_link_between_documents_resolves():
    broken = []
    for doc in _docs():
        if _COMPILED_INTO_ONE_PAGE in doc.as_posix():
            continue
        text = doc.read_text(encoding="utf-8", errors="replace")
        for target in re.findall(r"\]\((?!https?://|mailto:|#)([^)\s]+)\)", text):
            path = target.split("#", 1)[0]
            if path and not (doc.parent / path).resolve().exists():
                broken.append(f"{doc.relative_to(REPO_ROOT).as_posix()} -> {target}")
    assert not broken, "links to files that do not exist:\n  " + "\n  ".join(broken)


def test_every_in_page_anchor_resolves():
    broken = []
    for doc in _docs():
        if _COMPILED_INTO_ONE_PAGE in doc.as_posix():
            continue
        text = doc.read_text(encoding="utf-8", errors="replace")
        heads = {_slug(m.group(1)) for m in re.finditer(r"(?m)^#{1,6}\s+(.*)$", text)}
        for anchor in re.findall(r"\]\(#([^)\s]+)\)", text):
            if anchor not in heads:
                broken.append(f"{doc.relative_to(REPO_ROOT).as_posix()} -> #{anchor}")
    assert not broken, "anchors with no matching heading:\n  " + "\n  ".join(broken)


def test_no_document_advertises_a_flag_the_script_rejects():
    """deploy/server/README.md offered --compat long after it was removed.

    The installer does not ignore it, it dies on it - so anyone following that
    README got an error instead of a server.
    """
    installer = (REPO_ROOT / "deploy/scripts/install-server.sh").read_text(encoding="utf-8")
    removed = re.findall(r'--([a-z-]+)\)\s*\n\s*die "--\1 was removed', installer)
    assert removed, "expected install-server.sh to still reject at least one removed flag"
    offenders = []
    for doc in _docs():
        if "planning" in doc.as_posix() or "CHANGELOG" in doc.name:
            continue  # historical records are allowed to mention what once existed
        text = doc.read_text(encoding="utf-8", errors="replace")
        for flag in removed:
            for line in text.splitlines():
                if f"--{flag}" in line and not re.search(
                    r"removed|no longer|rejects|gone|does not exist", line, re.I
                ):
                    offenders.append(f"{doc.relative_to(REPO_ROOT).as_posix()}: {line.strip()[:90]}")
    assert not offenders, "documents still advertising a removed flag:\n  " + "\n  ".join(offenders)


def test_the_licence_is_stated_consistently():
    """The root README used to say "add your license here if distributing"
    while LICENSE was already The Unlicense and the commercial pages relied on
    it. Which one a reader believed changed what they thought they could do."""
    licence = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "public domain" in licence.lower()
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## License", 1)[1]
    assert "Unlicense" in section or "public domain" in section.lower(), (
        "the root README does not state the actual licence"
    )
    assert "Add your license here" not in readme


@pytest.mark.parametrize(
    "readme,canonical",
    [
        ("deploy/windows/README.md", "docs/deployment/03-windows-lan.md"),
        ("deploy/community/README.md", "docs/deployment/01-vm-docker.md"),
        ("deploy/server/README.md", "docs/deployment/02-linux-bare-metal.md"),
        ("docs/help/06b_server_installation.md", "docs/deployment/"),
        ("frontend/README.md", "docs/deployment/09-local-development.md"),
    ],
)
def test_secondary_readmes_point_at_their_canonical_guide(readme, canonical):
    """Each of these used to be a second, drifting copy of a full guide.

    deploy/windows/README.md called itself "the condensed checklist" while being
    a parallel twelve-step install; it is now an inventory of the files in that
    directory plus a pointer.
    """
    text = (REPO_ROOT / readme).read_text(encoding="utf-8")
    assert canonical in text, f"{readme} does not point at {canonical}"


def test_a_secondary_readme_does_not_restate_a_whole_install():
    """Length is a crude proxy, but a directory README that has grown into a
    full walkthrough is exactly how the duplication came back last time."""
    for readme, limit in [
        ("deploy/windows/README.md", 120),
        ("deploy/community/README.md", 160),
        ("deploy/server/README.md", 120),
        ("frontend/README.md", 80),
    ]:
        lines = len((REPO_ROOT / readme).read_text(encoding="utf-8").splitlines())
        assert lines <= limit, (
            f"{readme} is {lines} lines (limit {limit}). It has probably grown "
            f"back into a second copy of its guide; move the detail into the "
            f"canonical page and leave a pointer."
        )


def test_history_is_curated_instead_of_shipping_completed_work_logs():
    planning_dir = REPO_ROOT / "docs/planning"
    assert not planning_dir.exists() or not any(planning_dir.iterdir())
    index = REPO_ROOT / "docs/history/README.md"
    assert index.is_file(), "docs/history has no concise evidence index"
    text = index.read_text(encoding="utf-8").lower()
    assert "not published in end-user help" in text
    assert "changelog" in text and "deployment/10-operations" in text


def test_unfinished_commercial_and_point_in_time_audit_drafts_are_not_shipped():
    removed = (
        "docs/PRODUCTION_HARDENING_BASELINE.md",
        "docs/commercial/RETENTION_AND_DELETION.md",
        "docs/commercial/SECURITY_DISCLOSURE.md",
        "docs/commercial/SERVICE_AND_SUPPORT.md",
        "docs/security/csp_inline_burndown.md",
        "docs/security/dependency_advisory_triage.md",
    )
    assert not [path for path in removed if (REPO_ROOT / path).exists()]
