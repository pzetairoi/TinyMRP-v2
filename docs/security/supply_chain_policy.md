# Supply-chain pin and release-gate policy

This policy covers TinyMRP's production Docker image, supported Compose and
guided VPS/Caddy deployments, GitHub Actions, dependency audits, SBOMs, image
scanning, and repository secret scanning.

## Immutable defaults

The Dockerfile pins its BuildKit frontend, Node build stage, and Python runtime
stage to multi-architecture manifest digests. Main Compose, Windows one-folder,
guided VPS/Caddy, restore verification, and Nextcloud renderers pin Mongo,
Nginx, Caddy, MariaDB, and Nextcloud in the same way. Every third-party GitHub
Action uses a verified 40-character commit SHA with its release version in a
comment. CI uses Ubuntu 24.04, Python 3.11.15, pip 26.2, Node 24.18.1,
ShellCheck v0.11.0 by image digest, Trivy v0.72.0, and Syft v1.50.0 explicitly.

Tags remain alongside digests for operator readability and Dependabot context;
the digest determines the content that runs. Do not replace `tag@sha256:...`
with a tag alone.

## Updating a pin

Review pins monthly, before every release, and immediately for an applicable
high/critical advisory.

1. Resolve the proposed tag from the official registry or repository. For a
   Docker image, record the multi-architecture manifest digest, not an
   architecture-specific child digest. For an Action, resolve and review the
   tag's peeled commit.
2. Review upstream release notes and applicable advisories. Never accept a
   digest change whose tag or source revision was not independently verified.
3. Update every protected reference and its source contract. Dockerfile pins
   live in `docker/app/Dockerfile`; static deployment pins live in both Compose
   files; guided Caddy/Mongo/Nextcloud pins live in
   `deploy/scripts/lib/common.sh`, `deploy/scripts/lib/nextcloud.sh`, and the
   restore verifier.
4. Run `tests/test_supply_chain_contract.py`, bootstrap and six VPS/Caddy
   contracts, actionlint, Bash syntax, ShellCheck, both static Compose configs,
   rendered guided and Nextcloud Compose, and rendered Caddy validation.
5. Build the production image with `--pull`, run the complete backend suite,
   scan the final image with the pinned Trivy version, and exercise a disposable
   Mongo → TinyMRP → Caddy health request.
6. Record the old/new tag, digest/SHA, verification date, commands, test counts,
   scan disposition, and rollback commit in `docs/planning/hardeningplan.txt` and the release
   notes. Commit pin updates separately from feature work.

The Compose/rendering defaults support controlled emergency overrides through
`TINYMRP_MONGO_IMAGE`, `TINYMRP_NGINX_IMAGE`, `TINYMRP_CADDY_IMAGE`,
`TINYMRP_MARIADB_IMAGE`, and `TINYMRP_NEXTCLOUD_IMAGE`. An override must itself
use a reviewed `tag@sha256:digest`, be recorded in the change ticket, and be
folded back into source immediately after validation. The normal guided
VPS/Caddy path must not be replaced or bypassed.

## Evidence and blocking behavior

CI retains these artifacts for 30 days even when the matching gate fails:

- `backend-supply-chain`: `pip-audit.json` and backend CycloneDX SBOM;
- `frontend-supply-chain`: `npm-audit.json` and frontend lockfile CycloneDX SBOM;
- `image-supply-chain`: `trivy-image.json` and final-image CycloneDX SBOM.

Python, frontend, image, and full-history secret checks are blocking. The image
must have no fixed HIGH/CRITICAL findings. Proposed vulnerability exceptions do
not change CI until a named human risk owner records acceptance, date, maximum
90-day expiry, compensating controls, and voiding conditions.

Gitleaks extends the upstream default rules and checks full history. Its only
ignored fingerprint is a verified non-secret test fixture that has been
replaced; a regression prevents broader ignores. Two findings in a deleted
`.env.example` revision remain unsuppressed and release-blocking until an owner
classifies them and confirms rotation if they were ever usable credentials.

## Residual reproducibility limits

Runtime and CI package versions are exact, npm uses lockfile integrity hashes,
and the final image contains no pip/setuptools/wheel toolchain. Python source
artifacts are not yet installed under `pip --require-hashes`; `SUPPLY-LOCK-01`
tracks that remaining provenance control. GitHub-hosted runner internals and
external vulnerability databases are also time-varying evidence inputs, so
release records must retain the workflow run, SBOMs, audit JSON, image digest,
and scan date.
