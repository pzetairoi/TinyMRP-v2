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
    assert source.count('python-version: "3.11.15"') == 2
    assert source.count('node-version: "24.18.1"') == 1
    assert source.count("python -m pip install --upgrade pip==26.2") == 2
    assert "koalaman/shellcheck:v0.11.0@sha256:" in source
    assert "apt-get install" not in source


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
    assert "version: v0.72.0" in source
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


def test_application_build_stages_use_verified_manifest_digests():
    dockerfile = Path("docker/app/Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith(
        "# syntax=docker/dockerfile:1@sha256:"
        "87999aa3d42bdc6bea60565083ee17e86d1f3339802f543c0d03998580f9cb89"
    )
    assert (
        "FROM node:24-alpine@sha256:"
        "f70403e87646dc51b45295f4b8b70cdad0b63d2297c4c9899119b03f7af7a6b3 AS fe"
        in dockerfile
    )
    assert (
        "FROM python:3.11-slim-bookworm@sha256:"
        "b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba AS app"
        in dockerfile
    )
    assert "apt-get" not in dockerfile
    assert "urllib.request.urlopen('http://localhost:8000/api/ready', timeout=4)" in dockerfile
    assert "python -m pip check" in dockerfile
    assert "python -m pip uninstall -y setuptools wheel" in dockerfile
    assert "python -m pip uninstall -y pip" in dockerfile


def test_supported_compose_and_guided_deployment_images_are_digest_pinned():
    main_compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    onefolder_compose = Path("docker-compose.onefolder.yml").read_text(encoding="utf-8")
    common = Path("deploy/scripts/lib/common.sh").read_text(encoding="utf-8")
    nextcloud = Path("deploy/scripts/lib/nextcloud.sh").read_text(encoding="utf-8")
    restore = Path("deploy/scripts/restore-instance.sh").read_text(encoding="utf-8")

    mongo = (
        "mongo:6.0@sha256:"
        "8b6d8f5bbedb25cb73517b65cf99f13aeb75ad5b157a56c479287a840bbad3ac"
    )
    nginx = (
        "nginx:1.27-alpine@sha256:"
        "65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10"
    )
    caddy = (
        "caddy:2-alpine@sha256:"
        "5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648"
    )
    mariadb = (
        "mariadb:11@sha256:"
        "efb4959ef2c835cd735dbc388eb9ad6aab0c78dd64febcd51bc17481111890c4"
    )
    nextcloud_image = (
        "nextcloud:apache@sha256:"
        "58bc73331d541e0efe46c517ff7539e2e43427342b2a2feeb013b186fb4f3ecd"
    )

    for compose in (main_compose, onefolder_compose):
        assert f"${{TINYMRP_MONGO_IMAGE:-{mongo}}}" in compose
        assert f"${{TINYMRP_NGINX_IMAGE:-{nginx}}}" in compose

    for marker in (mongo, caddy, mariadb, nextcloud_image):
        assert common.count(marker) == 1
    assert 'image="$(caddy_image)"' in common
    assert common.count('"$(caddy_image)"') == 3
    assert "image: $(mariadb_image)" in nextcloud
    assert "image: $(nextcloud_image)" in nextcloud
    assert '"$(mongo_image)"' in restore


def test_worker_count_is_sized_to_the_host_not_hardcoded():
    """Two workers with four threads is eight concurrent requests per instance.

    A single part page fires roughly a dozen, so browsing a large assembly
    saturated the pool and the server appeared to hang until requests timed
    out. The image shipped that limit to every deployment regardless of the
    hardware underneath it.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    dockerfile = (repo_root / "docker/app/Dockerfile").read_text(encoding="utf-8")
    entrypoint = (repo_root / "docker/app/entrypoint.sh").read_text(encoding="utf-8")

    assert '"-w", "2"' not in dockerfile, "the fixed worker count is back"
    assert "WEB_CONCURRENCY" in entrypoint
    assert "nproc" in entrypoint
    # Floor and cap: a single-core box must not self-block, and workers are not
    # free - each holds its own Mongo pool and memory.
    # Floor and cap are deliberately conservative: a host may run several
    # instances side by side, and the first attempt at this - (2 x cores) + 1
    # floored at 4 - exhausted a shared VPS and took production down with it.
    assert "-lt 2" in entrypoint
    assert "-gt 6" in entrypoint
    assert "several instances" in entrypoint, "the multi-tenant warning must survive"
    # An operator must still be able to override it.
    assert 'if [ -z "${WEB_CONCURRENCY:-}" ]' in entrypoint
