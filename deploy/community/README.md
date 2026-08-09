# TinyMRP Community

This package installs one TinyMRP instance with authenticated MongoDB and
Redis. Linux and Windows Docker Desktop use the same `compose.yaml` and the
same hardened Linux application image. It does not include Nextcloud and does
not change the multi-instance VPS deployment under `deploy/scripts/`.

The installers ask only for the deliverables folder, access mode and address,
administrator credentials, and an explicit released version. They generate
the database and Flask secrets locally. The image repository is configured by
the signed/versioned package; do not use a version named `latest`.

## Linux

Extract the release's Community bundle, then run the local script:

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
- `domain` enables the optional Caddy profile. The app remains published only
  on loopback while Caddy owns public ports 80/443 and obtains HTTPS.

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
credentials.

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
