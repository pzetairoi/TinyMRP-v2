# Community acceptance matrix

Support is earned per host path. A rendered Compose file or a successful image
build is not a substitute for installing, preserving data, backing it up, and
restoring it on that host class.

| Host / mode | Install and auth | Backup / restore | Update rollback | Uninstall preserves data | Status |
| --- | --- | --- | --- | --- | --- |
| Ubuntu 24.04 CI, localhost | `install.sh` clean-volume job | real dump, content check, marker restore | lifecycle logic covered; registry failure exercised in host acceptance | named Mongo volume inspected and restarted | Automated on every relevant change |
| Windows Docker Desktop, localhost | `install.ps1` from an empty project/volume, authenticated Mongo, administrator, cleared bootstrap secret and writable bind mount | real 14 KB dump; post-backup marker removed by restore | nonexistent version failed and automatically restored the healthy prior image | default uninstall kept volume and administrator | Passed 2026-08-09; repeat from a versioned public bundle at release |
| Ubuntu/Debian, LAN | not yet run on a clean release host | not yet run | not yet run | not yet run | Release checklist |
| Windows Docker Desktop, LAN | not yet run with Private-only firewall rule | not yet run | not yet run | not yet run | Release checklist |
| Linux, domain/Caddy | Caddyfile validates and profile renders; real DNS/ACME not yet run | same data path as localhost | not yet run | not yet run | Do not call supported until real DNS/TLS acceptance passes |

## Release checklist

For each row being promoted to supported:

1. Start from a clean host and a versioned Community release bundle.
2. Run the platform installer without editing `.env`.
3. Log in, import a small pack, open a part/BOM/file path, and restart.
4. Confirm Mongo and Redis expose no host ports and the app hardening flags are
   present.
5. Create a database backup and a backup including deliverables; verify hashes
   and restore both to a disposable installation.
6. Update to the candidate version, then exercise a deliberately bad target to
   prove automatic image rollback.
7. Uninstall normally and prove data returns after `start`.
8. For LAN, test from a second device and confirm Windows rules (if used) are
   Private-network-only. For domain, prove HTTP redirects, a trusted automatic
   certificate, Secure cookies, HSTS, and renewal configuration.
9. Record host OS, Docker/Compose versions, image digest, result, and operator.

The signed Setup.exe layer and linux/arm64 remain later work. arm64 must not be
added to release metadata until dependency build and runtime smoke pass on that
architecture.
