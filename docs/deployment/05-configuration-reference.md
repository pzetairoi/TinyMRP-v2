# 05 — Configuration reference

Every environment variable TinyMRP reads, what it defaults to, and when
changing it is the right move.

Configuration is supplied as environment variables. Where they come from
depends on the deployment:

| Path | File | Applied by |
| --- | --- | --- |
| Docker Compose (VM/server) | `deploy/community/.env` | `docker compose --env-file` |
| Source-build Compose | `.env.docker` (from `.env.docker.example`) | `docker compose --env-file` |
| Linux bare metal | `/etc/tinymrp/.env` | systemd `EnvironmentFile=` |
| Windows LAN | `C:\TinyMRP\config\.env.lan` | `ENV_FILE` read by the service |
| VPS multi-instance | `/srv/tinymrp/instances/<name>/.env` | compose `env_file:` |
| Local development | `.env.dev` (from `.env.dev.example`) | `ENV_FILE=.env.dev python run.py` |

After changing any of these, restart the application. Nothing here is read
again at runtime — the two exceptions are noted where they occur.

---

## Contents

- [The three that matter](#the-three-that-matter)
- [Addressing, cookies and TLS](#addressing-cookies-and-tls)
- [Secrets](#secrets)
- [Database](#database)
- [Files and storage](#files-and-storage)
- [Uploads](#uploads)
- [Authentication and sessions](#authentication-and-sessions)
- [Rate limiting](#rate-limiting)
- [Content Security Policy](#content-security-policy)
- [Logging and diagnostics](#logging-and-diagnostics)
- [Data model and presentation](#data-model-and-presentation)
- [First-run seeding](#first-run-seeding)
- [Removed settings](#removed-settings)

---

## The three that matter

A minimal working configuration is four lines, and two of them are generated:

```bash
TINYMRP_URL=http://192.168.1.50:5000
FILES_LOCAL_ROOT=/srv/tinymrp/deliverables
SECRET_KEY=<32+ random characters>
SECURITY_PASSWORD_SALT=<a different 32+ random characters>
```

Plus `MONGO_URI` when MongoDB is not on `localhost:27017`.

---

## Addressing, cookies and TLS

### `TINYMRP_URL`

**Default:** unset. **Format:** an absolute URL including the scheme.

The address a browser uses to reach this instance. This is the single most
important setting after the secrets, because its **scheme** decides two
behaviours that a wrong guess breaks completely:

| Scheme | Session cookie | CSP | Effect of getting it wrong |
| --- | --- | --- | --- |
| `https://` | marked `Secure` | includes `upgrade-insecure-requests` | On a plain-HTTP site: the browser discards the cookie (login loops for ever) and rewrites every script/stylesheet/image to `https://` on a port that speaks HTTP (blank, unstyled page). |
| `http://` | not marked `Secure` | no upgrade directive | On an HTTPS site: the cookie could travel over plain HTTP if the user ever reaches the host without TLS. |

Include the port when it is not the scheme default:

```bash
TINYMRP_URL=http://192.168.1.50:5000     # LAN, non-standard port
TINYMRP_URL=http://tinymrp.lan           # LAN, nginx on 80
TINYMRP_URL=https://tinymrp.example.com  # behind TLS
```

A value with no scheme is a **startup error**, deliberately: guessing would
silently pick a security posture.

When it is unset, TinyMRP falls back to `INSTANCE_URL` (written by the guided
VPS installer), then to the first entry of `TINYMRP_ALLOWED_ORIGINS`, and
finally assumes **HTTPS**. That last default is what every deployment got
before this setting existed, so upgrading changes nothing for an
already-working HTTPS instance.

The resolved decision is logged on every start:

```
Browser transport: plain HTTP (TINYMRP_URL=http://192.168.1.50:5000)
SECURITY: TinyMRP is serving http://192.168.1.50:5000 without TLS, so session
cookies and passwords cross the network in clear text...
```

### `TINYMRP_BROWSER_TLS`

**Default:** `auto`. **Values:** `true`, `false`, `auto`.

Overrides the posture derived from `TINYMRP_URL`. You should almost never need
it — set `TINYMRP_URL` correctly instead. Legitimate use: a proxy topology
where the public URL genuinely cannot be expressed in one value.

### `TINYMRP_TRUSTED_PROXY_HOPS`

**Default:** `1`.

How many reverse proxies you control sit in front of the app, controlling how
many `X-Forwarded-For` / `X-Forwarded-Proto` / `X-Forwarded-Host` entries are
believed.

| Topology | Value |
| --- | --- |
| nginx or Caddy in front (all guided installers) | `1` |
| Application port published directly (community `localhost`/`lan`, `python run.py`) | `0` |
| CDN in front of your own proxy | `2` |

Set `0` when nothing overwrites those headers. Otherwise a client can send its
own `X-Forwarded-For`, which gives each request a private rate-limit bucket and
writes a forged address into the audit log.

### `TINYMRP_ALLOWED_ORIGINS`

**Default:** `TINYMRP_URL`'s origin.

Comma-separated CORS allowlist. Only relevant for a **different** origin
calling the API from a browser — the SPA is same-origin and the SolidWorks
add-in uses bearer tokens, so neither needs an entry. `*` or `all` allows any
origin and forces credentials off.

```bash
TINYMRP_ALLOWED_ORIGINS=http://localhost:5000,http://localhost:5173
```

### `TINYMRP_CORS_CREDENTIALS`

**Default:** `false`. Allow cookies on cross-origin requests. Only ever applies
to origins that matched the explicit allowlist.

### `FORCE_HTTPS`

**Default:** `false`. Redirects every plain-HTTP request to `https://` with a
301 and forces the TLS posture on. Use only where TLS genuinely terminates in
front of the app; on a LAN deployment it makes the site unreachable.

---

## Secrets

### `SECRET_KEY` (required)
### `SECURITY_PASSWORD_SALT` (required)

Minimum 16 characters, must differ from each other, and must not be a
placeholder (`change-me`, `default`, `secret`, …). **The application refuses to
start without them.** It never generates its own: a key invented at boot
changes on restart, and an application that re-keys itself cannot tell a forged
session from a real one.

```bash
openssl rand -hex 32
# or, on Windows:
powershell -c "[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')"
```

Changing `SECRET_KEY` signs out every user and invalidates every issued file
link. Changing `SECURITY_PASSWORD_SALT` invalidates **every stored password**;
treat it as permanent once users exist.

Every guided installer generates both. Keep a copy alongside your database
backups: without them a restored database has no usable sessions.

---

## Database

### `MONGO_URI`

**Default:** `mongodb://localhost:27017/tinymrp-v2`

```bash
# Local, no auth (development only)
MONGO_URI=mongodb://127.0.0.1:27017/tinymrp-v2

# Container stack with a scoped application user
MONGO_URI=mongodb://tinymrp_app:PASSWORD@mongo:27017/tinymrp?authSource=tinymrp

# Replica set
MONGO_URI=mongodb://user:pass@a:27017,b:27017,c:27017/tinymrp?replicaSet=rs0&authSource=admin
```

TinyMRP warns loudly on every start when the connection is unauthenticated and
not loopback. Enabling authentication on an **existing** data volume needs the
users created first — see
[UPDATING_PRODUCTION.md](../UPDATING_PRODUCTION.md) and
`deploy/scripts/enable-mongo-auth.sh`.

### `TINYMRP_REQUIRE_MONGO_AUTH`

**Default:** `false`. `true` turns the unauthenticated-Mongo warning into a
refusal to start. Recommended once auth is configured, so a misconfiguration
cannot silently fall back to an open database.

---

## Files and storage

### `FILES_LOCAL_ROOT` (required)

The folder holding the deliverables tree. On Windows use forward slashes.
TinyMRP reads CAD exports from it and writes thumbnails (`thumbs/`), uploads
and extra files (`extra/`) into it, so it must be writable by the account or
container user running the app (UID 1000 in the containers).

Expected subfolders, created automatically on container start:
`3mf bom datasheet dxf edr extra pdf pic ply png reports step stl temp thumbs`

`FILE_ROOT_LOCAL` is a legacy alias, still accepted.

### `FILES_URL_PREFIX`

**Default:** empty. The URL prefix a reverse proxy serves the deliverables
under (`/deliverables`). Only used when `FILES_PUBLIC_URLS=true`; with the
default, managed files are fetched through the app as `/files/view/<token>` and
this value is informational.

`FILE_ROOT_HTTP` is a legacy alias.

### `FILES_PUBLIC_URLS`

**Default:** `false`. `true` makes the app emit direct `FILES_URL_PREFIX` URLs
so a reverse proxy can serve the bytes. Faster for large files, but the proxy
then becomes responsible for authorisation — the shipped nginx configs do this
with an `auth_request` subrequest to `/files/auth`. Leave `false` unless you
have tested that path.

### `FILES_TOKEN_TTL_SECONDS`

**Default:** `86400` (24 h). Lifetime of a signed file link. `0` disables
expiry.

### `FILES_ALLOW_LEGACY_TOKENS`

**Default:** `false`. Accept pre-TTL non-expiring tokens during a migration
window. Turn off again afterwards.

### `FILES_ACCEL_REDIRECT_PREFIX`

**Default:** empty. Enables nginx `X-Accel-Redirect` offload for managed files
(`/__files`). Requires a matching `internal` nginx location. **Leave empty for
Caddy** — it has no equivalent, and setting it produces broken downloads.

### `EXTRA_FILES_ROOT` / `EXTRA_FILES_ALLOWED`

**Defaults:** `FILES_LOCAL_ROOT`, and `true`. Where user-attached extra files
live, and whether attaching them is permitted at all.

### `FILE_HASH_MAX_BYTES`

**Default:** `0` (no limit). Skip SHA-256 hashing of files larger than this.
Raise scan speed on very large assemblies at the cost of change detection.

### `MACRO_FILES_ROOT`

Folder served by the `/downloads/macro` route for the SolidWorks macro.

### `FILES_UPSTREAM_BASE` / `FILES_UPSTREAM_ALLOWED_HOSTS` / `FILES_PROXY_MAX_BYTES`

For the optional HTTP file proxy (`/deliverables/*`, `/extfiles/*`), used when
the deliverables live behind another HTTP server rather than on a local mount.
IP-literal upstreams are refused unless explicitly allowlisted, redirects are
never followed, and `FILES_PROXY_MAX_BYTES` (default 200 MB) caps a response.
Most deployments leave all three empty.

### `READINESS_MIN_FREE_DISK_MB`

**Default:** `512`. `/api/ready` fails below this much free space on the
deliverables volume, so an orchestrator stops sending work that a full disk
would corrupt mid-write. `0` disables the check.

---

## Uploads

| Variable | Default | Meaning |
| --- | --- | --- |
| `UPLOAD_PACK_MAX_ZIP_MB` | `1024` | Largest upload pack archive. |
| `UPLOAD_PACK_MAX_FILE_MB` | `1024` | Largest single file inside a pack. |
| `UPLOAD_PACK_MAX_FILES` | `5000` | Most files in one pack. |
| `TINYMRP_MAX_CONTENT_MB` | `min(UPLOAD_PACK_MAX_ZIP_MB, 200)` | Hard HTTP request cap, applied before the body is read. |
| `EXCEL_COMPILE_MAX_BYTES` | `10485760` | Largest spreadsheet the BOM compiler accepts. |

`TINYMRP_MAX_CONTENT_MB` is the one people miss: raising only the pack limits
still yields HTTP 413, because the request is rejected before it reaches the
importer. Raise your reverse proxy's body limit to match
(`client_max_body_size` in nginx; Caddy has no limit by default).

---

## Authentication and sessions

| Variable | Default | Meaning |
| --- | --- | --- |
| `SECURITY_PASSWORD_LENGTH_MIN` | `12` | Minimum password length (floor of 8). |
| `REMEMBER_COOKIE_DAYS` | `7` | "Remember me" lifetime. Flask-Login's own default is 365 days; this caps it. |
| `SECURITY_TWO_FACTOR_ENABLED` | `false` | Enable TOTP authenticator apps. |
| `SECURITY_TWO_FACTOR_REQUIRED` | `false` | Require it for everyone rather than offering it. |
| `SECURITY_TOTP_SECRETS` | — | Required when 2FA is on; encrypts per-user TOTP keys at rest. Generate with `python -c "from passlib import totp; print(totp.generate_secret())"`. |
| `API_TOKEN_DEFAULT_TTL_DAYS` | `90` | Default lifetime of a new API token. |
| `API_TOKEN_MAX_TTL_DAYS` | `365` | Ceiling a user may choose. |

Session lifetime is 30 minutes of inactivity, sliding. Cookies are always
`HttpOnly` and `SameSite=Strict`; the `Secure` flag follows
[`TINYMRP_URL`](#tinymrp_url).

---

## Rate limiting

| Variable | Default | Meaning |
| --- | --- | --- |
| `RATE_LIMIT_ENABLED` | `true` | Master switch. |
| `RATE_LIMIT_STORAGE_URI` | `memory://` | Where counters live. |
| `RATE_LIMIT_LOGIN` | `10 per minute;100 per hour` | Login and password endpoints. |
| `RATE_LIMIT_API` | unset | Optional global `/api/*` budget per client. |
| `RATE_LIMIT_EXPENSIVE` | per-route | Override for expensive endpoints. |
| `RATE_LIMIT_FAIL_CLOSED` | `false` | On a storage outage, reject instead of allowing through. |

With the `memory://` default, every gunicorn worker keeps its own counters, so
the real budget is the configured one **multiplied by the worker count**. Any
deployment with more than one worker should point this at Redis:

```bash
RATE_LIMIT_STORAGE_URI=redis://redis:6379/0
```

All container stacks do this already. A single-process Waitress service on
Windows does not need it.

Rate limits are keyed by client address, so they are only meaningful if
[`TINYMRP_TRUSTED_PROXY_HOPS`](#tinymrp_trusted_proxy_hops) matches reality.

---

## Content Security Policy

| Variable | Default | Meaning |
| --- | --- | --- |
| `SECURITY_HEADERS_ENABLED` | `true` | Emit CSP and the other security headers. |
| `TINYMRP_CSP_ALLOW_INLINE` | `true` | Allow inline `<script>`. Required by the legacy Jinja admin pages. |
| `TINYMRP_CSP_REPORT_ONLY_STRICT` | `false` | Also emit the stricter policy as report-only, to size the migration before enforcing it. |
| `TINYMRP_CSP_REPORT_URI` | unset | Where browsers post those reports. |

`upgrade-insecure-requests` is emitted only when the transport is HTTPS. See
[docs/security/csp_inline_burndown.md](../security/csp_inline_burndown.md).

---

## Logging and diagnostics

| Variable | Default | Meaning |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `LOG_FORMAT` | `text` | `json` for one JSON object per line. |
| `TINYMRP_PROFILE` | unset | Enables the request profiler. Registers nothing when unset, so it costs nothing in production. |
| `APP_VERSION` | `VERSION` file | Reported by `/api/health`. |
| `GIT_COMMIT` | unset | Build identifier reported alongside it. |
| `TINYMRP_BACKUPS_DIR` | `/data/backups` | Where the admin dashboard looks for backup archives (read-only). |
| `ENV_FILE` | unset | Path to the env file to load. Values in it override the process environment. |

---

## Data model and presentation

| Variable | Default | Meaning |
| --- | --- | --- |
| `APP_TIMEZONE` | `UTC` | IANA zone for displayed timestamps. Administrators can override it in the dashboard, which then wins. |
| `HARDWARE_FOLDERS` | `toolbox,fasteners,fastener,hardware` | Folder-name tokens marking library/fastener parts. Comma or semicolon separated. |
| `FLAT_PATTERN_PAGE_NAMES` | `flatpattern` | Drawing page labels dropped from binders. |
| `PROCESS_META_FILE` | bundled | Override the process metadata catalogue. |
| `ARENA_FILE_LINK_BASE_URL` | empty | Base URL for deep links into Arena PLM. |

Each of these is also editable from **Admin → Settings**, and the stored value
wins over the environment.

---

## First-run seeding

| Variable | Default | Meaning |
| --- | --- | --- |
| `TINYMRP_SEED_ADMIN` | `false` | Create the first administrator on an **empty** user collection. |
| `TINYMRP_ADMIN_EMAIL` | — | Required when seeding. |
| `TINYMRP_ADMIN_PASSWORD` | — | Required when seeding; 12+ characters. |
| `ALLOW_PERMISSION_TEST_DATA` | `false` | Initial default for the demo/permission-test environment. Administrators can toggle it in the dashboard afterwards, and the stored value then wins. |

Seeding never modifies an existing user: with any user present it reports
`existing-users-skip` and moves on, which is what makes it safe to leave
enabled in a persisted environment file. Guided installers still blank the
password after first boot.

See [06 — First run](06-first-run.md).

---

## Removed settings

| Setting | Status |
| --- | --- |
| `TINYMRP_SECURITY_MODE` | **Removed.** Compat mode selected a second set of CORS, CSRF, cookie and upload rules. There is one security model now and the variable is ignored. |
| `install-server.sh --compat` | **Removed.** The script exits with an explanation. |
| Runtime secret generation (`instance/runtime_secrets.json`) | **Removed.** `SECRET_KEY` and `SECURITY_PASSWORD_SALT` must be supplied. |
| Legacy add-in API endpoints | **Removed.** The add-in authenticates with API bearer tokens. |
