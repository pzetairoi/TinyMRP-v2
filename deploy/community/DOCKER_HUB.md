# Docker Hub publishing and image use

The public image target is `tinymrp/tinymrp`, subject to namespace ownership
being confirmed. Repository administrators enable it without changing the
workflow by setting:

- repository variable `PUBLISH_DOCKERHUB=true`;
- optional repository variable `DOCKERHUB_IMAGE` (defaults to
  `tinymrp/tinymrp`);
- secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`.

On a semantic version tag, `release-image.yml` runs the existing Trivy
HIGH/CRITICAL gate and CycloneDX SBOM first, then one build step publishes the
same `linux/amd64` digest and tags to GHCR and every enabled registry. Stable
tags also move `latest`; prerelease tags do not. Published semantic version
tags are immutable. v1.0.0 is never retagged by this work.

The image is one component, not a complete `docker run` installation. Users
should download the matching Community bundle from the GitHub release and run
its local installer. The bundle pins both the repository and version in
`release.env`, creates authenticated MongoDB on an empty named volume, keeps
Mongo/Redis off host ports, generates secrets, and binds the chosen
deliverables folder.

Do not put passwords on a `docker run` command line, publish `.env`, or install
with `latest`. The release page carries the Community archives, Trivy JSON,
and SBOM that correspond to the image.

`linux/arm64` is deliberately absent until dependency build and runtime smoke
pass on real arm64. Adding a platform is a release-contract change, not a
metadata-only edit.
