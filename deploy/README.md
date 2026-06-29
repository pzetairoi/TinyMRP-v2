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
- `install-nextcloud.sh`
- `doctor.sh`

If your checkout did not preserve executable bits, run them as `bash ./deploy/scripts/<script>.sh ...` instead of `./deploy/scripts/<script>.sh ...`.

## What the scripts create

Host-level state is stored under `/srv/tinymrp`:

- `/srv/tinymrp/host/.env`
- `/srv/tinymrp/caddy/Caddyfile`
- `/srv/tinymrp/caddy/routes/*.caddy`
- `/srv/tinymrp/instances/<instance_name>/`
- `/srv/tinymrp/nextcloud/`

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

## 3. Install Nextcloud on the same host

Use the same DNS and Caddy flow:

```bash
sudo ./deploy/scripts/install-nextcloud.sh cloud.tinymrp.com
```

What it does:

- validates DNS like the TinyMRP installer
- starts private Nextcloud and MariaDB containers
- adds the Nextcloud Caddy route
- lets Caddy manage HTTPS automatically

## 4. Run deployment checks

```bash
sudo ./deploy/scripts/doctor.sh
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
- Nextcloud DNS and endpoint health if installed

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
