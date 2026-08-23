# Supply-chain and release policy

This maintainer policy covers production images, supported Compose variants,
deployment renderers, GitHub Actions, dependency audits, SBOMs, image scanning
and repository secret scanning. It is not end-user Help.

## Immutable, reviewable inputs

- Production and service images use reviewed `tag@sha256:digest` references.
- Third-party GitHub Actions use reviewed commit SHAs.
- Python runtime requirements are paired with a hash-locked requirements file;
  npm uses its committed lockfile and integrity hashes.
- Release evidence identifies the source commit, image digest and scan date.

Do not replace a digest/SHA with a floating tag. Tags may remain beside digests
for readability; the immutable identifier decides what runs.

## Updating a dependency or pin

1. Resolve the proposed version from the official registry/repository and read
   its release notes and applicable advisories.
2. For images, record the multi-architecture manifest digest. For Actions,
   record the reviewed commit SHA.
3. Update every protected reference and its contract test. Regenerate the
   Python or npm lockfile when its direct inputs change.
4. Run the relevant unit, integration, deployment-rendering and supply-chain
   contract tests.
5. Build the production image with current bases, run the complete application
   suite, scan the image and exercise health/readiness against a disposable
   stack.
6. Record old/new versions, immutable identifiers, verification commands and
   rollback target in the change/release record.

Emergency image overrides must also use reviewed immutable references, be
recorded with the change, and be folded back into source promptly.

## Blocking gates and evidence

CI retains dependency-audit JSON, backend/frontend/image SBOMs, image-scan
output and secret-scan results. Runtime dependency, image and full-history
secret checks are blocking according to the workflow configuration.

A vulnerability exception requires the record defined in
[`risk_acceptance_template.md`](risk_acceptance_template.md). An exception does
not alter a CI gate until the authorised configuration and its narrow contract
test are reviewed together.

## Verification scope

Pin updates must cover static Compose files, generated deployment variants,
restore verification and relevant install/update scripts. A green application
test alone is not evidence that a deployment or supply-chain change is safe.

Current commands and exact tool versions live in the workflows and lockfiles;
those executable sources are authoritative over prose.
