# Guided Ubuntu Deployment

This is the recommended Linux deployment path for TinyMRP production hosts.

Default behavior:

- Caddy is the reverse proxy.
- Caddy manages HTTPS certificates automatically.
- TinyMRP app containers stay private behind Caddy.
- Protected deliverables stay on the normal TinyMRP app route when Caddy fronts the instance.
- MongoDB stays private and is never published on the host.
- Each TinyMRP instance gets its own private Docker network and database.
- All public traffic enters through the shared `tinymrp_proxy` Docker network.

The scripts live in `deploy/scripts/`:

- `install-host.sh`
- `create-instance.sh`
- `install-nextcloud-instance.sh`
- `install-nextcloud.sh`
- `link-nextcloud-instance.sh`
- `doctor.sh`
- `update-repo.sh`
- `update-instance.sh`
- `update-all-instances.sh`
- `rollback-instance.sh`

If your checkout did not preserve executable bits, run them as `bash ./deploy/scripts/<script>.sh ...` instead of `./deploy/scripts/<script>.sh ...`.

## What the scripts create

Host-level state is stored under `/srv/tinymrp`:

- `/srv/tinymrp/host/.env`
- `/srv/tinymrp/caddy/Caddyfile`
- `/srv/tinymrp/caddy/routes/*.caddy`
- `/srv/tinymrp/instances/<instance_name>/`
- `/srv/tinymrp/nextcloud/<instance_name>/`
- `/srv/tinymrp/nextcloud/<instance_name>/links/*.env`

Legacy shared/global Nextcloud, if you intentionally keep using it, remains under:

- `/srv/tinymrp/nextcloud/.env`
- `/srv/tinymrp/nextcloud/compose.yml`
- `/srv/tinymrp/nextcloud/links/*.env`

Host config in `/srv/tinymrp/host/.env` includes:

- `PUBLIC_IPV4`
- `PUBLIC_IPV6`
- `ACME_EMAIL`
- `REVERSE_PROXY=caddy`
- `DEFAULT_BASE_DOMAIN`
- `LOCAL_VM_MODE`

## 1. Install host services

Run this once per host:

```bash
sudo ./deploy/scripts/install-host.sh
```

Optional flags:

```bash
sudo ./deploy/scripts/install-host.sh \
  --acme-email ops@example.com \
  --base-domain tinymrp.com \
  --local-mode http
```

What it does:

- installs Docker Engine and the Compose plugin
- installs `dnsutils`
- detects public IPv4 and IPv6 where possible
- asks for the ACME email if it is not already saved
- creates `/srv/tinymrp/host/.env`
- creates the shared Docker network `tinymrp_proxy`
- starts a shared Caddy container on ports `80` and `443`

## 2. Create a TinyMRP instance

The normal production path only needs:

- instance name
- final public domain

Examples:

```bash
sudo ./deploy/scripts/create-instance.sh company1 company1.tinymrp.com
sudo ./deploy/scripts/create-instance.sh company1 company1.com
```

What the script does:

- detects the host IP again
- prints the exact DNS record to create
- waits for the domain to resolve to the host IP
- creates the instance under `/srv/tinymrp/instances/company1`
- generates:
  - MongoDB database name
  - app secret key
  - password salt
  - admin password if you do not provide one
  - compose project name
  - container names
  - private network name
  - deliverables path
- starts the instance with Docker Compose
- adds or updates the Caddy route
- reloads Caddy safely

Optional flags:

```bash
sudo ./deploy/scripts/create-instance.sh company1 company1.tinymrp.com --skip-dns-check
sudo ./deploy/scripts/create-instance.sh company1 company1.tinymrp.com --admin-email admin@company1.tinymrp.com
sudo ./deploy/scripts/create-instance.sh company1 company1.test.local --local-mode internal-tls
```

## Protected deliverables under Caddy

New guided instances are generated with:

- `FILES_LOCAL_ROOT="/data/deliverables"`
- `FILES_URL_PREFIX="/deliverables"`
- `FILES_PUBLIC_URLS="false"`
- `FILES_ACCEL_REDIRECT_PREFIX=""`

The bind mount stays:

- `/srv/tinymrp/instances/<instance>/deliverables:/data/deliverables`

This is intentional. In the default guided deployment, Caddy proxies requests to the TinyMRP app and protected deliverables are served through the normal TinyMRP file route. `FILES_ACCEL_REDIRECT_PREFIX="/__files"` is an Nginx `X-Accel-Redirect` setting and must stay empty for Caddy unless you explicitly build and validate a Caddy-compatible protected static offload flow.

## DNS and domain setup

The script prints the exact record name and value. Use the examples below to check what to expect.

### A. TinyMRP subdomain under `tinymrp.com`

Domain:

- `company1.tinymrp.com`

Expected DNS:

- `A company1 <server-ip>`
- optional `AAAA company1 <server-ipv6>`

### B. Customer subdomain

Domain:

- `tinymrp.customercompany.com`

Expected DNS:

- `A tinymrp <server-ip>`
- optional `AAAA tinymrp <server-ipv6>`

### C. Customer root domain

Domain:

- `customercompany.com`

Expected DNS:

- `A @ <server-ip>`
- optional `AAAA @ <server-ipv6>`
- optional `CNAME www customercompany.com`

### D. Nextcloud

Domain:

- `cloud.tinymrp.com`

Expected DNS:

- `A cloud <server-ip>`
- optional `AAAA cloud <server-ipv6>`

## DNS validation behavior

For public domains, the scripts check DNS before HTTPS is started.

Checks:

- A record must resolve to the detected IPv4
- AAAA is checked only when the host has IPv6 configured
- if AAAA is missing, the scripts continue with IPv4 only
- if DNS points somewhere else, the scripts wait and let you retry

Skip this only when you mean it:

```bash
sudo ./deploy/scripts/create-instance.sh company1 company1.tinymrp.com --skip-dns-check
```

## 3. Install per-company Nextcloud on the same host

The recommended multi-company path is one independent Nextcloud per TinyMRP company instance:

```bash
sudo ./deploy/scripts/install-nextcloud-instance.sh company1 cloud.company1.tinymrp.com
sudo ./deploy/scripts/install-nextcloud-instance.sh company2 cloud.company2.tinymrp.com
```

What it does:

- validates that the matching TinyMRP instance exists first
- creates `/srv/tinymrp/nextcloud/<instance_name>/`
- writes per-instance `.env` and `compose.yml`
- starts private Nextcloud and MariaDB containers with unique names
- connects only the Nextcloud app container to the shared Caddy proxy network
- adds a per-instance Caddy route such as `nextcloud-company1.caddy`
- lets Caddy manage HTTPS automatically
- generates admin credentials automatically
- keeps TinyMRP deliverables outside Nextcloud's internal data folder

Legacy shared/global mode still exists for backwards compatibility:

```bash
sudo ./deploy/scripts/install-nextcloud.sh cloud.tinymrp.com
```

That installs one shared Nextcloud under `/srv/tinymrp/nextcloud`. It is not the recommended path for multi-company deployments, and it will not automatically re-domain or overwrite an existing legacy install.

## 4. Link TinyMRP deliverables into Nextcloud

After a company Nextcloud is installed, link that company instance with one command:

```bash
sudo ./deploy/scripts/link-nextcloud-instance.sh company1
sudo ./deploy/scripts/link-nextcloud-instance.sh company2 --read-only --non-interactive
```

By default, `link-nextcloud-instance.sh <instance>` now targets the same-name Nextcloud instance under `/srv/tinymrp/nextcloud/<instance>`.

What it does:

- prompts for the access mode unless you pass a flag
- defaults to the safer read-only mode
- writes a managed `/srv/tinymrp/nextcloud/<nextcloud_instance>/compose.tinymrp-deliverables.override.yml` for TinyMRP deliverables mounts
- preserves unrelated user `compose.override.yml` content
- recreates only the Nextcloud `app` container when the mount configuration changes
- enables the Nextcloud `files_external` app automatically
- creates the Nextcloud group `tinymrp-<instance>` if needed
- adds the configured Nextcloud admin user to that group
- creates or updates the external local storage entry `TinyMRP - <instance> Deliverables`
- points the storage to `/mnt/tinymrp-deliverables/<instance>`
- runs `php occ files:scan --all`
- verifies the mount from inside the Nextcloud container
- verifies the requested read-only or bidirectional mount mode
- installs `acl` and applies ACLs for UID `1000` and UID `33` only when bidirectional mode is requested

Access modes:

- Read-only is the default and safest mode. Nextcloud can view, download, and share TinyMRP deliverables, but cannot modify or delete them.
- Bidirectional mode is required when Windows or Mac Nextcloud desktop clients must upload or sync files back into `/srv/tinymrp/instances/<instance>/deliverables`.
- Bidirectional mode is higher risk because Nextcloud users can modify or delete files that TinyMRP uses.

Recommended default:

- use read-only for customer sharing and download workflows
- use bidirectional only for trusted internal sync workflows

Non-interactive examples:

```bash
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --read-only
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --bidirectional
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --non-interactive --read-only
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --non-interactive --bidirectional
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --nextcloud-instance global --read-only --non-interactive
```

`--non-interactive` requires either `--read-only` or `--bidirectional`.

If you explicitly need to keep using one legacy shared/global Nextcloud, target it with:

```bash
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --nextcloud-instance global --read-only --non-interactive
```

Mount behavior:

- read-only mode: `/srv/tinymrp/instances/<instance>/deliverables:/mnt/tinymrp-deliverables/<instance>:ro`
- bidirectional mode: `/srv/tinymrp/instances/<instance>/deliverables:/mnt/tinymrp-deliverables/<instance>:rw`

The script is idempotent:

- it does not duplicate Docker mounts
- it does not duplicate Nextcloud external storage entries
- it detects and prints the existing access mode
- it can upgrade a linked instance from read-only to bidirectional
- it asks for confirmation before downgrading from bidirectional to read-only

Safety notes:

- TinyMRP remains the storage owner for `/srv/tinymrp/instances/<instance>/deliverables`
- deliverables are not moved into Nextcloud internal data
- the script does not use `chmod 777`
- the confirmed Caddy deliverables fix stays unchanged: `FILES_ACCEL_REDIRECT_PREFIX=""`

To unlink one instance without touching TinyMRP data:

```bash
sudo ./deploy/scripts/link-nextcloud-instance.sh company1 --remove
```

## 5. Run deployment checks

```bash
sudo ./deploy/scripts/doctor.sh
sudo ./deploy/scripts/doctor.sh --instance company1
sudo ./deploy/scripts/doctor.sh --nextcloud-instance company1
sudo ./deploy/scripts/doctor.sh --all
```

It checks:

- Caddy is installed and running
- Caddy config validates
- ports `80` and `443` are listening
- firewall rules for `80` and `443`
- public IPv4 and IPv6 detection
- each instance route points to the correct app container
- each app container prints `FILES_LOCAL_ROOT` and can read it
- each host deliverables folder is mounted into the app container
- Caddy instances are not using a non-empty `FILES_ACCEL_REDIRECT_PREFIX`
- `/__files` is not configured unless a matching reverse-proxy internal file route exists
- each instance domain resolves to the expected IP
- each instance endpoint responds
- MongoDB is not exposed publicly
- each per-instance Nextcloud root exists
- Nextcloud DNS and endpoint health if installed
- Nextcloud MariaDB is not exposed publicly
- linked TinyMRP deliverables still exist on the host
- Nextcloud can see each linked `/mnt/tinymrp-deliverables/<instance>` path
- linked Nextcloud Docker mounts match the configured read-only or bidirectional mode
- linked external storage entries and Nextcloud groups exist
- the configured Nextcloud admin user belongs to the matching group
- bidirectional mounts are writable from inside Nextcloud when enabled
- deliverables are not being mounted inside Nextcloud's internal data directory

## Legacy shared/global Nextcloud

If you already have a legacy shared/global Nextcloud under `/srv/tinymrp/nextcloud`, leave it in place unless you plan a manual migration.

- the deployment scripts do not delete it
- the deployment scripts do not re-domain it automatically
- new per-company installs should go under `/srv/tinymrp/nextcloud/<instance_name>`
- if you need to keep linking to that legacy install, use `--nextcloud-instance global`

## 6. Update the repository

Run repository updates from the central TinyMRP checkout saved in `TINYMRP_REPO_ROOT`:

```bash
cd /opt/TinyMRP-v2
sudo ./deploy/scripts/update-repo.sh
```

Useful variants:

```bash
sudo ./deploy/scripts/update-repo.sh --ref main --alias latest
sudo ./deploy/scripts/update-repo.sh --ref v2.1.0 --alias stable
sudo ./deploy/scripts/update-repo.sh --ref 0123456789abcdef --force
```

What it does:

- checks Git working tree status first
- refuses to continue if local changes exist unless `--force` is passed
- fetches from the configured remote
- moves the repo to the requested branch, tag, or commit
- builds `tinymrp-app:<short_commit>`
- optionally updates `tinymrp-app:latest` or `tinymrp-app:stable` after a successful build
- records host-side build metadata under `/srv/tinymrp/host/releases/<timestamp>/`

What it does not do:

- it does not touch `/srv/tinymrp/instances/*`
- it does not restart any company instance
- it does not touch MongoDB data or deliverables

## 7. Update one instance

After `update-repo.sh` builds the target image, update one instance at a time:

```bash
sudo ./deploy/scripts/update-instance.sh company1
```

To pin or test a specific image:

```bash
sudo ./deploy/scripts/update-instance.sh company1 --image tinymrp-app:abc123def456
sudo ./deploy/scripts/update-instance.sh company1 --image tinymrp-app:stable --git-commit 0123456789abcdef
```

What it does:

- creates a per-run backup under `/srv/tinymrp/instances/<instance>/updates/<timestamp>/backup/`
- stores update metadata and logs under `/srv/tinymrp/instances/<instance>/updates/<timestamp>/`
- regenerates `compose.yml` from the current template while preserving instance-specific values from `.env`
- updates only the app image tag in the compose file
- recreates only the `app` container by default
- leaves MongoDB running unless an operator explicitly performs a database restore during rollback
- runs health checks and `doctor.sh --instance <instance> --skip-host-checks`
- restores the previous compose file and previous app image automatically if post-update verification fails

Backed up before each update:

- instance `.env`
- instance `compose.yml`
- current per-instance update state
- the generated Caddy route file for that instance, if present

Never touched by the normal update path:

- `deliverables/`
- MongoDB data under `mongo/`
- Caddy routes, unless you separately change the instance domain
- generated secrets in `.env`

## 8. Update all instances

Roll out the currently built image to every instance one by one:

```bash
sudo ./deploy/scripts/update-all-instances.sh
```

Optional:

```bash
sudo ./deploy/scripts/update-all-instances.sh --continue-on-error
sudo ./deploy/scripts/update-all-instances.sh --image tinymrp-app:stable --git-commit 0123456789abcdef
```

This script:

- enumerates all instance env files under `/srv/tinymrp/instances/*/.env`
- calls `update-instance.sh` for each instance in sequence
- stops on the first failure by default
- prints a summary of updated, skipped, failed, and rolled-back instances

## 9. Roll back one instance

Roll back the most recent app update for one instance:

```bash
sudo ./deploy/scripts/rollback-instance.sh company1
```

This restores:

- the previous app image tag
- the previous generated `compose.yml`

This does not restore by default:

- MongoDB data
- deliverables

If you have an operator-managed MongoDB backup and explicitly want to restore it during rollback:

```bash
sudo ./deploy/scripts/rollback-instance.sh company1 --restore-mongo-from /srv/backups/company1-mongo-20260630.tar.gz
```

The script requires interactive confirmation before replacing MongoDB data.

## Update metadata and version tracking

Each instance stores update records under:

- `/srv/tinymrp/instances/<instance>/updates/`

Each run records:

- previous Git commit
- new Git commit
- previous image tag
- new image tag
- timestamp
- update log path
- backup path
- health and doctor results

The latest deployed app version is also recorded in `updates/current.env` for each instance.

## Migrations and pinned versions

If a release requires a database migration or any manual data conversion:

1. Do not start with `update-all-instances.sh`.
2. Take an operator-managed MongoDB backup outside the normal update scripts.
3. Run `update-repo.sh` first.
4. Update one pilot instance with `update-instance.sh`.
5. Validate the release notes, app health, imports, deliverables, and exports before continuing.

To keep one instance on an older tested build, pin it explicitly:

```bash
sudo ./deploy/scripts/update-instance.sh company1 --image tinymrp-app:abc123def456 --git-commit 0123456789abcdef
```

You can also use `rollback-instance.sh` to return to the previous recorded version.

## Deliverables smoke test

After creating or updating an instance, run this regression check:

1. Create a small Upload Pack that includes files under `deliverables/png` and `deliverables/pdf`.
2. Import the Upload Pack in TinyMRP and confirm the BOM is created.
3. Verify the imported files exist on the host under `/srv/tinymrp/instances/<instance>/deliverables`.
4. Verify the app container sees the same files under `/data/deliverables`.
5. Verify TinyMRP can display or download those files through the normal `/deliverables` route after import.
6. Verify the response path does not depend on a `"/__files"` redirect in the default Caddy deployment.

## Recover an existing broken Caddy instance

If an older instance was generated with `FILES_ACCEL_REDIRECT_PREFIX="/__files"`, clear it and recreate the app container:

```bash
cd /srv/tinymrp/instances/<instance>
sudo cp .env ".env.bak.$(date +%Y%m%d-%H%M%S)"
sudo sed -i 's#^FILES_ACCEL_REDIRECT_PREFIX=.*#FILES_ACCEL_REDIRECT_PREFIX=""#' .env
sudo docker compose up -d --force-recreate
```

## Local VM mode

For local-only testing, use a local domain and skip public certificate flow.

Examples:

```bash
sudo ./deploy/scripts/install-host.sh --local-mode http
sudo ./deploy/scripts/create-instance.sh demo demo.test.local --local-mode http
sudo ./deploy/scripts/create-instance.sh demo demo.localhost --local-mode internal-tls
```

Rules:

- local domains such as `company1.test.local` and `company1.localhost` do not use public Let's Encrypt certificates
- `--local-mode http` keeps the site on HTTP
- `--local-mode internal-tls` uses `tls internal` in Caddy

Add a hosts-file entry on the client machine that will open the site:

```text
192.168.56.20 demo.test.local
```

For real public HTTPS testing in a VM:

- the domain must resolve publicly to the VM or VPS public IP
- ports `80` and `443` must be reachable from the internet

## Safety notes

- Do not publish MongoDB ports.
- Do not commit generated `.env` files from `/srv/tinymrp`.
- Do not edit generated Caddy route files by hand unless you also own the deployment workflow.
- If a route already exists and would be changed, the scripts ask before overwriting it.
