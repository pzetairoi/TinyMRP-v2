# TinyMRP Community

This package installs one TinyMRP instance with authenticated MongoDB and
Redis. Linux and Windows Docker Desktop use the same `compose.yaml` and the
same hardened Linux application image. It does not include Nextcloud and does
not change the multi-instance VPS deployment under `deploy/scripts/`.

The step-by-step guide with every option, firewall recipe and failure mode is
[`docs/deployment/01-vm-docker.md`](../../docs/deployment/01-vm-docker.md).
This page is the summary.

Download `tinymrp-community-VERSION.zip` (Windows) or `.tar.gz` (Linux) from
the matching GitHub release. Each bundle carries a generated `release.env`
that pins the image repository and exact semantic version. A source checkout
does not — run the installer with `--build` (`-Build` on Windows) there and it
builds the same Dockerfile the release pipeline builds, tagged
`tinymrp-local:<VERSION>-src.<git-sha>`.

The installers ask only for the deliverables folder, access mode and address,
and administrator credentials. They generate the database and Flask secrets
locally, and write `TINYMRP_URL` so the application knows whether browsers
reach it over TLS. Do not use a version named `latest`.

| Linux | Windows | Effect |
| --- | --- | --- |
| `--build` | `-Build` | Build the app image from this checkout instead of pulling a published one. |
| `--with-demo-data` | `-WithDemoData` | Install the CV03 sample dataset and one demo login per role, printing the passwords once. Evaluation instances only. |

## Linux

From a source checkout:

```bash
chmod +x deploy/community/install.sh deploy/community/tinymrp.sh
./deploy/community/install.sh --build --with-demo-data
./deploy/community/tinymrp.sh status
```

From an extracted release bundle:

```bash
chmod +x install.sh tinymrp.sh
./install.sh
./tinymrp.sh status
```

## Windows

Install and start Docker Desktop, extract the Community bundle, and double
click `install.cmd` (or run `powershell -File .\install.ps1`). The default
deliverables folder is `C:\TinyMRP\Deliverables`.

Do not use a remote `irm | iex` command. Download a versioned release bundle,
inspect or verify it, extract it, and run its local installer.

## Access modes

- `localhost` is the default and binds only `127.0.0.1`.
- `lan` is explicit opt-in and binds `0.0.0.0`; secure the host and firewall.
  It serves plain HTTP, so logins cross the network in clear text and the app
  logs a warning on every start. Supported for trusted private networks only.
- `domain` enables the optional Caddy profile. The app remains published only
  on loopback while Caddy owns public ports 80/443 and obtains HTTPS.

Each mode writes a matching `TINYMRP_URL` into `.env`. Its scheme is what tells
the application whether to mark session cookies `Secure` and whether to emit
`upgrade-insecure-requests` — both correct over HTTPS, both fatal over plain
HTTP. If you change `APP_PORT` or the access mode by hand, change `TINYMRP_URL`
with it, or login will silently loop.

Set public DNS to the host before choosing domain mode. Windows firewall
changes are never automatic; the installer can add a Private-network-only
rule after showing exactly what it will do.

## Commands

Linux uses `./tinymrp.sh COMMAND`; Windows uses
`.\tinymrp.ps1 COMMAND`. Supported commands are `start`, `stop`, `status`,
`logs`, `update`, `backup`, `restore`, and `uninstall`. Run a command without
its required arguments to see its usage.

`backup` always captures a real Mongo archive and the configuration, verifies
gzip integrity and uncompressed content size, and can optionally include the
deliverables folder. `restore` replaces the TinyMRP database from one of those
archives and optionally restores its deliverables snapshot. The configuration
copy is recovery evidence and is not silently applied over live database
credentials. Database restore is exact: collections created after the backup
are removed before the archive is replayed. Deliverables restore is deliberately
preservation-first and overlays the snapshot without deleting newer files.

`uninstall` preserves the Mongo volume, configuration, backups, and
deliverables by default. Only `uninstall --delete-data --yes` removes
Docker-managed volumes; it still never deletes the user-selected deliverables
folder or backup files.

## Capacity and versions

The image normally chooses a conservative Gunicorn worker count from host CPU.
Set `WEB_CONCURRENCY` in `.env` when memory measurements call for a lower fixed
limit.

Updates require an explicit semantic version tag and perform a verified backup
first. If the replacement app does not become healthy, the command restores
the previous image reference automatically. Database migrations may still
require restoring the newly-created backup; keep it until the update is fully
accepted.
