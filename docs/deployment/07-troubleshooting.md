# 07 — Troubleshooting

Symptoms first. Each entry says what you see, why it happens, and the exact fix.

- [Where to look first](#where-to-look-first)
- [Login and sessions](#login-and-sessions)
- [Startup failures](#startup-failures)
- [Files, thumbnails and uploads](#files-thumbnails-and-uploads)
- [Network and access](#network-and-access)
- [Database](#database)
- [Performance](#performance)
- [SolidWorks add-in](#solidworks-add-in)
- [Collecting a support bundle](#collecting-a-support-bundle)

---

## Where to look first

```bash
# container stacks
cd deploy/community
docker compose --env-file .env -f compose.yaml logs --tail 100 app
./tinymrp.sh status

# VPS instance
docker logs --tail 100 tinymrp-<instance>-app
sudo ./deploy/scripts/doctor.sh

# bare metal
sudo journalctl -u tinymrp -n 100 --no-pager
sudo systemctl status tinymrp

# Windows
Get-Service TinyMRP-App
Get-Content C:\TinyMRP\logs\tinymrp.log -Tail 100
```

The first fifteen lines of a start tell you most of what you need:

```
Loaded env file: /etc/tinymrp/.env
Env check: SECRET_KEY set? True; MONGO_URI present? True
Browser transport: plain HTTP (TINYMRP_URL=http://192.168.1.50:5000)
Rate limiting enabled (storage=redis://redis:6379/0, login=10 per minute;100 per hour)
```

Check the **Browser transport** line against how you actually reach the site.
That single line resolves most access problems.

Two endpoints answer without credentials:

```bash
curl http://<host>:<port>/api/health   # process is alive
curl http://<host>:<port>/api/ready    # Mongo reachable and disk has room
```

---

## Login and sessions

### I log in and land back on the login page

The commonest deployment fault, and the one with no error message.

**Cause.** `TINYMRP_URL` says `https://` but you are browsing over plain HTTP
(or it is unset, which assumes HTTPS). The session cookie is marked `Secure`,
the browser refuses to store it on a plain-HTTP origin, and the CSRF token
minted with the login form is gone before the form is posted.

**Confirm it in one command**, from a client machine:

```bash
curl -sSD - -o /dev/null http://192.168.1.50:5000/login | grep -i set-cookie
```

If the output contains `Secure` and you are using `http://`, that is the fault.
The startup log agrees:

```
Browser transport: HTTPS (no public address configured; assuming HTTPS)
```

**Fix.** Declare the real address and restart:

```bash
# in your env file
TINYMRP_URL=http://192.168.1.50:5000
```

```bash
# container stack
cd deploy/community && ./tinymrp.sh stop && ./tinymrp.sh start
# bare metal
sudo systemctl restart tinymrp
# Windows
Restart-Service TinyMRP-App
```

The log must now read `Browser transport: plain HTTP`, and the `Set-Cookie`
header must no longer contain `Secure`.

**Other causes of the same symptom**, in order of likelihood:

- The port in `TINYMRP_URL` does not match the port you browse to. The origin
  includes the port.
- Two addresses for one instance (IP for some users, hostname for others).
  Pick one for `TINYMRP_URL`; add the other to `TINYMRP_ALLOWED_ORIGINS`.
- A reverse proxy that does not forward cookies, or strips `Set-Cookie`.
- System clock skew of more than a few minutes between server and client.

### The page loads but has no styling, and the browser console shows failed https:// requests

Same root cause, second symptom. The CSP `upgrade-insecure-requests` directive
is rewriting every asset URL to `https://` on a port that speaks HTTP.

```bash
curl -sSD - -o /dev/null http://192.168.1.50:5000/login | grep -i content-security-policy
```

If it contains `upgrade-insecure-requests` on a plain-HTTP deployment, fix
`TINYMRP_URL` exactly as above.

### "The CSRF session token is missing"

The same lost-cookie problem, stated out loud. Fix `TINYMRP_URL`. If the
transport is already right, the user's browser is blocking cookies for the site
or an extension is stripping them.

### "The request origin did not match this TinyMRP instance"

The `Origin`/`Referer` header on an unsafe request does not match the host the
app received. Usually a proxy rewriting `Host` without setting
`X-Forwarded-Host`, or a `TINYMRP_TRUSTED_PROXY_HOPS` of 0 behind a
TLS-terminating proxy (so the app thinks the scheme is `http` while the browser
sent `https`). Set the hop count to match your topology — see
[08 — Networking](08-networking-and-tls.md#reverse-proxies-and-forwarded-headers).

### Users are signed out every 30 minutes

Working as designed: `PERMANENT_SESSION_LIFETIME` is 30 minutes of inactivity,
sliding on each request. "Remember me" extends it to `REMEMBER_COOKIE_DAYS`
(7).

### Everyone was signed out after an update

`SECRET_KEY` changed. Sessions are signed with it, so a new key invalidates
every one — and every previously issued file link. Restore the original value
from your configuration backup. If it is genuinely lost, users must sign in
again; nothing else is damaged.

### An administrator is locked out

```bash
flask --app run.py user bootstrap-admin --email admin@yourcompany.com
```

Creates or repairs the account, grants `administrator`, and revokes existing
sessions and tokens. It needs shell access to the host, by design.

### Too many login attempts

`RATE_LIMIT_LOGIN` defaults to 10 per minute and 100 per hour, per client
address. Wait, or restart the app to clear in-memory counters (a Redis-backed
store survives the restart). If a whole office shares one NAT address behind a
proxy and `TINYMRP_TRUSTED_PROXY_HOPS` is 0, they share one budget — set the
hop count correctly.

---

## Startup failures

### `SECRET_KEY must be set to a strong value.`

Missing, shorter than 16 characters, or a placeholder such as `change-me`.
TinyMRP never generates its own: a key invented at boot changes on restart, and
an application that re-keys itself cannot distinguish a forged session from a
real one.

```bash
openssl rand -hex 32
```

### `TINYMRP_URL=... has no scheme.`

Include `http://` or `https://`. Guessing would silently choose a security
posture.

### `TINYMRP_TRUSTED_PROXY_HOPS must be a non-negative integer.`

Use `0`, `1`, or `2`.

### `[bootstrap] configuration error: TINYMRP_ADMIN_PASSWORD is required...`

`TINYMRP_SEED_ADMIN=true` with no password. Supply both credentials, or set
seeding to `false` and use `flask user bootstrap-admin`.

### `[entrypoint] Bootstrap failed after 30 attempts`

The app could not reach MongoDB. Check `docker compose logs mongo`, confirm
`MONGO_URI` names the right host, and confirm the credentials match the volume
— Mongo only creates users on the **first** boot of an empty data directory, so
changing `MONGO_ROOT_PASSWORD` against an existing volume has no effect.

### `TCP port 5000 is already in use`

```bash
sudo ss -ltnp | grep :5000       # Linux
Get-NetTCPConnection -LocalPort 5000 -State Listen   # Windows
```

Stop the other service or pick another port — and update `TINYMRP_URL` to
match.

### `Set an explicit semantic TINYMRP_VERSION`

You are running the community installer from a clone, which has no
`release.env`. Add `--build` (Linux) or `-Build` (PowerShell) to build the
image locally.

### `.env already exists`

An installation is already here. Use `./tinymrp.sh` to operate it, or move
`.env` aside to start over. Moving it aside does not delete the database.

### The app container restarts in a loop

```bash
docker compose --env-file .env -f compose.yaml logs --tail 50 app
```

Usually a missing secret, an unreachable Mongo, or a deliverables mount that
does not exist on the host.

---

## Files, thumbnails and uploads

### `ERROR: deliverables root /data/deliverables is NOT writable by uid 1000`

The container runs as UID 1000 and writes thumbnails and uploads into the
deliverables tree.

```bash
sudo chown -R 1000:1000 /srv/tinymrp/deliverables
sudo chmod -R u+rwX,g+rX /srv/tinymrp/deliverables
```

On a VPS instance: `sudo ./deploy/scripts/fix-deliverables-permissions.sh <instance>`.

For an SMB/CIFS mount, ownership comes from the mount options, not `chown`:

```
//nas/cad /srv/tinymrp/deliverables cifs credentials=/etc/samba/creds,uid=1000,gid=1000,file_mode=0664,dir_mode=0775 0 0
```

### `these deliverables subfolders are NOT writable: extra thumbs temp`

The root is writable but some subfolders are not — normally after restoring a
backup as root. Same `chown -R`.

### Thumbnails do not appear

1. Are there PNG files for the part? Thumbnails are generated from the PNG
   exports, not from CAD geometry.
2. Is `<root>/thumbs` writable?
3. Regenerate: `flask --app run.py thumbs rebuild-all` (or `rebuild-one --pn X`).
4. Re-scan the part: `flask --app run.py files scan-one --pn X --rev A`.

### Files are listed but download 404s

The database has a record whose file is no longer on disk — a restored database
without its deliverables, or a moved folder. Confirm `FILES_LOCAL_ROOT` points
where the files actually are, then re-scan.

### HTTP 413 on upload

The request exceeded a cap. There are three, and raising only one does nothing:

```bash
UPLOAD_PACK_MAX_ZIP_MB=2048
TINYMRP_MAX_CONTENT_MB=2048       # defaults to min(zip, 200) — the usual culprit
```

Plus the reverse proxy: `client_max_body_size 2048m;` in nginx. Caddy has no
default limit.

### Upload succeeds but no parts appear

Open the import journal in the UI. The importer reports per-part blocks — an
unreleased parent, a missing permission, or a part number that does not match
the numbering scheme. A dry run shows the same plan without writing:

```bash
flask --app run.py import zip --file pack.zip --dry-run
```

---

## Network and access

### Works on the server, not from another machine

1. `APP_BIND_IP` must be `0.0.0.0`, not `127.0.0.1`. In the community
   installer that is the difference between `localhost` and `lan` mode.
2. Host firewall — see
   [08 — Firewall recipes](08-networking-and-tls.md#firewall-recipes).
3. Is the client on the same subnet, or is there a VLAN/router ACL in between?
4. From the client: `nc -zv 192.168.1.50 5000`, then
   `curl http://192.168.1.50:5000/api/health`.

### The domain resolves but Caddy will not get a certificate

Let's Encrypt validates over port 80 from the internet. Confirm the public DNS
`A` record points at this host, that inbound 80 and 443 reach it, and check
`docker compose logs caddy`. Repeated failures hit rate limits — test with a
staging endpoint first.

### Reverse proxy returns 502

The app is not answering on its upstream port. Confirm it is listening
(`ss -ltnp | grep 8000`), that the proxy names the right host and port, and
that a container proxy is on the same Docker network.

---

## Database

### `SECURITY: MongoDB has no authentication configured`

Warned on every start. Fine on loopback for development; not acceptable for
anything networked. Enabling auth on an existing volume needs the users created
first: `deploy/scripts/enable-mongo-auth.sh` and
[UPDATING_PRODUCTION.md](../UPDATING_PRODUCTION.md). Set
`TINYMRP_REQUIRE_MONGO_AUTH=true` afterwards so a regression cannot pass
silently.

### Authentication failed after changing a Mongo password

Mongo creates users only while initialising an **empty** data directory.
Changing `MONGO_ROOT_PASSWORD` in `.env` against an existing volume changes
nothing in the database and everything in the app's connection string. Restore
the old value, or change the password inside Mongo with `db.changeUserPassword`
and then update `.env`.

### Restoring a backup into a fresh host fails

A database backup is not sufficient on its own. You also need `SECRET_KEY`,
`SECURITY_PASSWORD_SALT` and the Mongo credentials from the configuration
backup, and the deliverables tree. `./tinymrp.sh backup` captures `config.env`
alongside the dump for exactly this reason — it is kept as recovery evidence
and is deliberately not applied automatically over live credentials.

---

## Performance

### Slow with several users

Check the worker count in the startup log:

```
2 core(s) -> 3 gunicorn workers (set WEB_CONCURRENCY to override...)
```

Each worker is a Python process with its own Mongo pool: 250–400 MB each. More
workers than the host can hold causes swapping, which is far worse than a
queue. On a host running several instances, pin `WEB_CONCURRENCY` per instance.

### Rate limits trigger far later than configured

With the default `memory://` storage, each worker keeps its own counters, so
the real budget is the configured one times the worker count. Point
`RATE_LIMIT_STORAGE_URI` at Redis. All container stacks already do.

### High idle CPU

Historically the Mongo healthcheck: `mongosh` is a full Node REPL, roughly
1.9 s of CPU per invocation. The interval is 30 s in the shipped configs. If
you have a hand-written compose file with a 10 s interval, raise it.

### Slow first search after every restart

Part-list indexes are built once at boot. If it recurs on every request, the
index creation is failing — check the startup log for an exception around
`ensure_active_part_field_indexes`.

---

## SolidWorks add-in

### Cannot connect

1. The backend URL must be exactly `TINYMRP_URL`, including scheme and port.
2. `curl <url>/api/health` from the CAD workstation.
3. The token must be valid — they expire after
   `API_TOKEN_DEFAULT_TTL_DAYS` (90). Issue a new one under **Account → API
   tokens**.
4. With a self-signed certificate, the workstation must trust it.

### 403 on a specific action

The token carries the user's permissions. The message names the missing
permission (`Missing permission: parts.write`). Grant the role that includes
it, or use an account that has it.

### 401 `token_required`

No token, or a revoked one. Changing a user's password or roles revokes their
tokens on purpose; issue a new one.

---

## Collecting a support bundle

```bash
mkdir -p /tmp/tinymrp-support && cd /tmp/tinymrp-support

# versions and health
docker compose --env-file ~/tinymrp/deploy/community/.env \
  -f ~/tinymrp/deploy/community/compose.yaml ps > containers.txt
curl -sS http://localhost:5000/api/health > health.json
curl -sS http://localhost:5000/api/ready  > ready.json

# logs
docker compose --env-file ... -f ... logs --no-color --tail 2000 app > app.log
docker compose --env-file ... -f ... logs --no-color --tail 200 mongo > mongo.log

# configuration WITHOUT secrets
grep -vE '(SECRET|PASSWORD|SALT|TOKEN)' ~/tinymrp/deploy/community/.env > env-redacted.txt

tar -czf ../tinymrp-support.tar.gz .
```

The admin dashboard also has **Admin → Diagnostics**, which shows the resolved
configuration with every secret redacted, plus the storage roots and what the
app can see in them.

Check `env-redacted.txt` by eye before sending it anywhere.
