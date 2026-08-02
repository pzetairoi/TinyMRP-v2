import re
from pathlib import Path

WORKFLOW_DIR = Path(".github/workflows")
ACTION_REF_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^#\s]+)", re.MULTILINE)


def _workflow(name: str) -> str:
    return (WORKFLOW_DIR / name).read_text(encoding="utf-8")


def test_workflows_pin_every_external_action_to_a_commit():
    workflow_paths = sorted(WORKFLOW_DIR.glob("*.yml"))
    assert workflow_paths

    for path in workflow_paths:
        source = path.read_text(encoding="utf-8")
        action_refs = USES_RE.findall(source)
        assert action_refs, f"{path} contains no action references"
        for action_ref in action_refs:
            if action_ref.startswith("./"):
                continue
            assert ACTION_REF_RE.fullmatch(action_ref), (
                f"{path} has mutable or malformed action reference {action_ref}"
            )


def test_security_workflow_uses_versioned_runner_and_full_history_secret_scan():
    source = _workflow("security.yml")

    assert "ubuntu-latest" not in source
    assert "runs-on: ubuntu-24.04" in source
    assert "fetch-depth: 0" in source
    assert "persist-credentials: false" in source
    assert "gitleaks/gitleaks-action@" in source


def test_dependency_reports_and_sboms_upload_before_blocking_gates():
    source = _workflow("security.yml")

    expected = (
        "pip-audit.json",
        "sbom-backend.cdx.json",
        "npm-audit.json",
        "sbom-frontend.cdx.json",
        "backend-supply-chain",
        "frontend-supply-chain",
        "if: always()",
        "Enforce Python dependency gate",
        "Enforce frontend dependency gate",
    )
    for marker in expected:
        assert marker in source

    assert source.index("Upload backend supply-chain evidence") < source.index(
        "Enforce Python dependency gate"
    )
    assert source.index("Upload frontend supply-chain evidence") < source.index(
        "Enforce frontend dependency gate"
    )


def test_release_scan_evidence_is_retained_before_publish_gate():
    source = _workflow("release-image.yml")

    assert "ubuntu-latest" not in source
    assert "trivy-image.json" in source
    assert "sbom-image.cdx.json" in source
    assert "continue-on-error: true" in source
    assert source.index("Upload image supply-chain evidence") < source.index(
        "Enforce image vulnerability gate"
    )
    assert source.index("Enforce image vulnerability gate") < source.index("Log in to GHCR")


def test_frontend_sbom_uses_the_pinned_directory_scanner():
    source = _workflow("security.yml")

    assert "uses: anchore/sbom-action@e22c389904149dbc22b58101806040fa8d37a610" in source
    assert "file: ./frontend/package-lock.json" in source
    assert "output-file: frontend/sbom-frontend.cdx.json" in source
    assert source.count("syft-version: v1.50.0") == 1
    assert "upload-artifact: false" in source
