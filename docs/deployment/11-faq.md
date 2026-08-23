# 11 — Deployment FAQ

Questions that come up before, during and after an install. Every answer here
has been checked against the running software, not inferred from the code.

- [Choosing a deployment](#choosing-a-deployment)
- [Configuration](#configuration)
- [Installing](#installing)
- [First login, users and demo data](#first-login-users-and-demo-data)
- [Other machines cannot reach it](#other-machines-cannot-reach-it)
- [HTTPS and certificates](#https-and-certificates)
- [Files and storage](#files-and-storage)
- [Shell and platform gotchas](#shell-and-platform-gotchas)
- [Operations](#operations)
- [Security posture](#security-posture)
- [SolidWorks add-in](#solidworks-add-in)

---

## Choosing a deployment

**Which one do I pick?**
One company, a VM or a spare machine, Docker allowed → [01 — VM with Docker](01-vm-docker.md).
Docker not allowed on Linux → [02 — bare metal](02-linux-bare-metal.md).
Windows office LAN → [03 — Windows LAN](03-windows-lan.md).
Several companies on one public host → [04 — VPS multi-instance](04-vps-multi-instance.md).

**Do I need Nextcloud?**
No. It is optional and exists only on the VPS path, as a file-sync front end.
It is installed only by scripts with `nextcloud` in the name. Skip them and
nothing about TinyMRP changes: the deliverables folder is then an ordinary
directory, filled by the SolidWorks add-in, upload packs, or your own sync
(rsync, Syncthing, an SMB mount).

**Do I need Docker?**
No — [02](02-linux-bare-metal.md) and [03](03-windows-lan.md) run natively. But
Docker gives you the tested installer, verified backups, and version-pinned
updates with automatic rollback. Prefer it where it is allowed.

**Can it run on the same machine as SolidWorks?**
Yes, for a small team. Give it 8 GB RAM and set `WEB_CONCURRENCY=2` so the
workers do not compete with CAD. Note the machine must stay on for others to
use TinyMRP.

**How much hardware?**
2 vCPU / 4 GB is the floor for one instance; 4 vCPU / 8 GB is comfortable. Add
~2 GB per extra instance on a multi-tenant host. Disk is dominated by
deliverables: your CAD export size, plus about 30% for thumbnails, plus backup
retention.

**Can I use an existing MongoDB?**
Yes. Set `MONGO_URI` and, on bare metal, pass `--mongo-uri` so the installer
skips installing its own. MongoDB 6.0 and 7.0 are what the deployments use.

**Can one host serve several companies?**
That is exactly the VPS path: separate database, deliverables tree, secrets,
domain and certificate per instance. Set `WEB_CONCURRENCY` per instance once
you pass two — the default sizes itself from host cores assuming it is alone.

**Air-gapped install?**
Yes. On a connected machine: `docker build -f docker/app/Dockerfile -t tinymrp-local:2.0.0 .`,
then `docker save` that image plus `mongo:6.0` and `redis:7-alpine` to a tar,
copy it across, `docker load`, and run the installer with
`TINYMRP_IMAGE_REPOSITORY=tinymrp-local TINYMRP_VERSION=2.0.0 TINYMRP_INSTALL_PULL=never`.

**ARM64 (Apple Silicon, Raspberry Pi, Graviton)?**
Not validated. The images are built and tested for linux/amd64 only. Do not put
arm64 into production before dependency build and runtime smoke pass there.

---

## Configuration

**What is the absolute minimum I must configure?**
Three things: the deliverables folder, `TINYMRP_URL`, and the port (optional,
defaults to 5000). The installers generate the secrets, the database
credentials, the first administrator password and the proxy configuration.

**What is `TINYMRP_URL` and why does the scheme matter so much?**
It is the address a user types, scheme included. Its scheme decides two things
that silently break a deployment when they are wrong:

| Declared | Cookies | CSP |
| --- | --- | --- |
| `https://` | marked `Secure` | `upgrade-insecure-requests` |
| `http://` | not marked `Secure` | no upgrade directive |

A `Secure` cookie is discarded by the browser on a plain-HTTP origin, so the
CSRF token minted with the login form is gone by the time the form is posted.
A LAN install with `TINYMRP_URL` incorrectly set to `https://` reports:

```
HTTP 400 — "CSRF session token is missing. Retry the action from the original form."
```

and the CSP header carried `upgrade-insecure-requests`, which rewrites every
script and stylesheet to `https://` on a port that speaks HTTP.

**Nothing showed this on my laptop.**
Browsers treat `localhost`, `127.0.0.1` and `::1` as *potentially trustworthy*
origins: they store `Secure` cookies over plain HTTP there and skip
`upgrade-insecure-requests`. A LAN IP gets neither exemption. A configuration
that assumes TLS therefore works perfectly on the developer machine and fails
the moment a second computer opens it.

**I changed the port and now login loops.**
The origin includes the port. Change `APP_PORT` **and** `TINYMRP_URL` together,
then restart.

**Some users type the IP, others a hostname.**
Pick one for `TINYMRP_URL` — generated links use that host. Add the other to
`TINYMRP_ALLOWED_ORIGINS` so browser API calls from it are accepted:

```bash
TINYMRP_URL=http://tinymrp.lan
TINYMRP_ALLOWED_ORIGINS=http://tinymrp.lan,http://192.168.1.50
```

**Do I have to restart after editing configuration?**
Yes. The environment is read once at start. Timezone, hardware folders, upload
caps and the demo toggle can also be changed in **Admin → Settings** at
runtime, and the stored value then wins over the environment.

**What happens if I lose `SECRET_KEY`?**
Everyone is signed out and every issued file link stops working. Nothing else
is damaged. Restore it from your configuration backup if you have one.

**Can I change `SECURITY_PASSWORD_SALT`?**
No, not after users exist. It invalidates **every stored password**. Treat it
as permanent.

**What is `TINYMRP_TRUSTED_PROXY_HOPS`?**
How many reverse proxies you control sit in front of the app. `1` for the
nginx/Caddy deployments, `0` when the app port is published directly. It
matters because `X-Forwarded-For` is plain client input unless a proxy you own
overwrites it — trust it with nothing in front and a client can rotate the
header to get a fresh rate-limit budget on every request.

**Where does the env file live?**
Docker Compose: `deploy/community/.env`. Source-build compose: `.env.docker`.
Bare metal: `/etc/tinymrp/.env`. Windows: `C:\TinyMRP\config\.env.lan`. VPS:
`/srv/tinymrp/instances/<name>/.env`. Dev: `.env.dev`.

---

## Installing

**"This is not a versioned Community bundle."**
You are running the installer from a git clone, which has no `release.env`. Add
`--build` (Linux) or `-Build` (PowerShell) to build the image locally.

**"TCP port 5000 is already in use."**
`sudo ss -ltnp | grep :5000`, or on Windows
`Get-NetTCPConnection -LocalPort 5000 -State Listen`. Stop the other service or
choose another port — and update `TINYMRP_URL` to match.

**".env already exists."**
An installation is already here. Operate it with `./tinymrp.sh`, or move `.env`
aside to start over. Moving it aside does not delete the database.

**How long does `--build` take?**
5–15 minutes the first time (it compiles the frontend and installs Python
wheels). Under a minute on later builds thanks to layer caching.

**Can I run the installer twice?**
No — it refuses when `.env` exists, deliberately, so it cannot overwrite live
secrets. Use `tinymrp.sh` for everything after the first run.

**Does the installer need root / Administrator?**
Linux: no, as long as your user is in the `docker` group. Windows: only to add
a firewall rule; it asks first and never adds one silently.

**Where did the administrator password go?**
The installer erases it from `.env` once the account exists, so the one-time
secret does not persist. Nothing can recover it — reset with
`flask user set-password --email <address>`.

---

## First login, users and demo data

**I set `TINYMRP_SEED_ADMIN=true` but no administrator was created.**
Seeding only ever runs on a **completely empty** user collection. With any user
present it reports, in the container log:

```
[bootstrap] {"admin": "existing-users-skip", ...}
```

That is the safety property that stops a restart resetting a live password. It
bites when you reuse a Docker volume from an earlier install. Either use a
fresh volume, or create the account explicitly:

```
flask --app run.py user bootstrap-admin --email admin@yourcompany.com
```

**What are the password rules?**
12+ characters (`SECURITY_PASSWORD_LENGTH_MIN`), not equal to the email, and
not the known example `ChangeMe123!`. The Community installers require 14+
for the first administrator.

**How do I get a dataset to test with?**
`flask --app run.py demo install` — 494 sample files, the CV03 assembly with
its BOM, and one login per role scenario. Passwords print once. Full detail in
[06 — First run](06-first-run.md).

**The sample parts appear but no drawing opens.**
Fixed in the current version. Records created by earlier builds pointed at the
copy of the fixture inside the application image, which is outside the
configured deliverables root, so the file resolver refused every one of them.
Re-run `flask --app run.py demo install`; it repairs the stored paths in place
and reports `part_files_repaired`.

**Where are the demo passwords?**
Printed once by `demo install` on stdout as JSON. Capture them:
`flask --app run.py demo install > demo-credentials.json`. Re-running rotates
them, invalidating the previous set.

**How do I remove the demo accounts?**
`flask --app run.py demo remove --disable`. Sample files stay in the
deliverables root on purpose — by then they may have been imported or
annotated.

**A customer or supplier login sees nothing.**
Correct until the user is linked to a customer or supplier record. The portal
boundary is fail-closed. Link it under **Admin → Customers/Suppliers**.

**Expected scoped demo behaviour:** the `customer_spares` account sees 4 parts
out of 70, gets 403 on `/admin/`, and cannot see the deliberately unreleased
`CV03-F02` revision B.

---

## Other machines cannot reach it

The most common support question for a LAN deployment. Run the diagnostic
first — it checks all six causes and prints the fix:

```powershell
.\deploy\windows\check_lan_access.ps1 -Port 5000
```

**1. Windows has classified the network "Public".**
This is the one nobody guesses. Windows applies a firewall rule only on the
profile(s) it is scoped to, and warns about nothing when none of them are
active. A rule scoped to Domain/Private is completely inert on a Public
network. Check and fix:

```powershell
Get-NetConnectionProfile
Set-NetConnectionProfile -InterfaceAlias "Ethernet" -NetworkCategory Private
```

Only for networks you trust. On the machine this was tested on, both adapters
were classified Public while the TinyMRP rules were scoped Domain,Private — so
those rules did nothing at all.

**2. Docker Desktop and the native service behave differently here.**
Docker Desktop ships its own inbound rules for `com.docker.backend`, and on the
tested machine those were scoped **Public** — so a Docker-published port stayed
reachable on a Public network while a native nginx listener on the same host
would not have been. Do not assume that because the Docker path works, the
native path will.

**3. A Block rule wins.**
Windows evaluates Block before Allow regardless of order.
`configure_firewall_lan.ps1` deliberately blocks 8000 and 27017 on **all**
profiles. If you move the app to one of those ports, remove the block:
`Remove-NetFirewallRule -DisplayName 'TinyMRP Block App Port'`.

**4. It is only listening on loopback.**
`netstat -an | findstr :5000` must show `0.0.0.0:5000`, not `127.0.0.1:5000`.
In the Community installer that is the difference between `localhost` and `lan`
access mode (`APP_BIND_IP`).

**5. The name does not resolve on the client.**
It resolving on the server proves nothing. Add an internal DNS A record, or a
hosts entry on each client.

**6. Something outside the host.**
A router or VLAN ACL, client-side security software, or wireless client
isolation — common on guest Wi-Fi, and it blocks device-to-device traffic
entirely. Test with `Test-NetConnection <server-ip> -Port <port>` from the
client.

**How do I prove it works from another machine?**

```bash
nc -zv 192.168.1.50 5000                        # or Test-NetConnection
curl http://192.168.1.50:5000/api/health
curl -sSD - -o /dev/null http://192.168.1.50:5000/login | grep -i set-cookie
```

The last one must **not** contain `Secure` on a plain-HTTP deployment.

**Can I test from WSL on the same machine instead?**
No. WSL-to-host traffic does not traverse the standard Windows Defender
Firewall profile rules, so it succeeds even when a real LAN client would be
blocked. This was confirmed by measurement. Use a genuinely separate device.

**Linux firewall equivalents**

```bash
sudo ufw allow from 192.168.1.0/24 to any port 5000 proto tcp
sudo firewall-cmd --permanent --zone=internal --add-port=5000/tcp && sudo firewall-cmd --reload
```

---

## HTTPS and certificates

**Is plain HTTP acceptable?**
On a trusted private network, yes — it is a supported, deliberate mode, and the
app logs a warning on every start. Passwords and session cookies cross the
network in clear text, so it is never acceptable for anything reachable from
the internet.

**How do I add HTTPS without a public domain?**
Three ways, best first: a real certificate for an internal name using a DNS-01
ACME challenge; your organisation's internal CA; or self-signed. See
[08 — Adding HTTPS to a LAN deployment](08-networking-and-tls.md#adding-https-to-a-lan-deployment).

**Self-signed certificates and the add-in?**
Every client must trust the certificate, including the SolidWorks workstations
— they will refuse the connection otherwise.

**Can I put it behind an existing reverse proxy?**
Yes. Forward `Host`, `X-Forwarded-For` and `X-Forwarded-Proto`, set
`TINYMRP_TRUSTED_PROXY_HOPS` to the number of proxies you control, set
`TINYMRP_URL` to the public address, and raise the body limit to match your
upload caps.

**Caddy will not issue a certificate.**
Let's Encrypt validates over port 80 from the internet. Confirm public DNS
points here and 80/443 are open, then read `docker logs tinymrp-caddy`.
Repeated failures hit rate limits — use the staging endpoint while testing.

---

## Files and storage

**Where do deliverables live and can it be a NAS or a Windows file share?**
Anywhere `FILES_LOCAL_ROOT` points, including an NFS or SMB/CIFS mount, as long
as it is mounted before the app starts and the app user can write to it. This
is the normal setup when a CAD team drops files straight onto a share instead
of uploading them through the browser.

Put the credentials in a root-only file, `/etc/tinymrp-fileshare.cred`:

```
username=SVC-TinyMRP
password=<the service account password>
domain=YOURDOMAIN
```

```bash
sudo chmod 600 /etc/tinymrp-fileshare.cred
```

Then one line in `/etc/fstab`:

```
//FILESERVER/CAD  /srv/tinymrp/deliverables  cifs  credentials=/etc/tinymrp-fileshare.cred,uid=1000,gid=1000,file_mode=0664,dir_mode=0775,vers=3.0,iocharset=utf8,_netdev,nofail  0  0
```

`_netdev` and `nofail` are not optional. Without `_netdev` the machine can try
to mount before the network is up; without `nofail` a share that is briefly
unreachable stops the boot at a maintenance prompt.

Two traps, both of which look like data loss:

1. **`uid=1000` only changes what Linux *displays*.** Write permission is still
   decided by the file server's ACL for the account in the credentials file. A
   share can show `drwxrwxr-x 1000 1000` in `ls -l` and still refuse every
   write. Ask whoever owns the file server to grant that account **modify**
   rights, then prove it with a real write rather than by reading `ls`:
   `sudo -u '#1000' touch /srv/tinymrp/deliverables/probe && rm /srv/tinymrp/deliverables/probe`
2. **A share that fails to mount leaves an empty local directory behind.** The
   bind mount then succeeds against nothing, TinyMRP starts normally, and every
   file appears to have vanished. `deploy/community/check-install.sh` checks for
   exactly this, including whether the mount has an `/etc/fstab` entry at all.

Verify the whole arrangement with:

```bash
./deploy/community/check-install.sh
```

**"deliverables root is NOT writable by uid 1000".**
The container runs as UID 1000 and writes thumbnails and uploads into the tree.
`sudo chown -R 1000:1000 /srv/tinymrp/deliverables`, or
`deploy/scripts/fix-deliverables-permissions.sh <instance>` on the VPS path.

**Should I set `FILES_PUBLIC_URLS=true`?**
Only if you have tested it. With the default `false`, every managed file is
fetched through the app as `/files/view/<token>` with permissions enforced in
one place. With `true`, the reverse proxy serves the bytes and authorises via a
subrequest to `/files/auth` — faster for large files, one more thing to get
right. Both paths are exercised by the shipped nginx configs.

**HTTP 413 on upload.**
Three caps, and raising one is not enough:
`UPLOAD_PACK_MAX_ZIP_MB`, `TINYMRP_MAX_CONTENT_MB` (defaults to
`min(zip, 200)` — the usual culprit), and the proxy's own body limit
(`client_max_body_size` in nginx; Caddy has none by default).

**Thumbnails are missing.**
They are generated from PNG exports, not CAD geometry. Confirm PNGs exist,
`<root>/thumbs` is writable, then `flask thumbs rebuild-all`.

**Files are listed but download 404s.**
The database has records whose files are not on disk — usually a database
restored without its deliverables. Check `FILES_LOCAL_ROOT`, then re-scan.

---

## Shell and platform gotchas

**Git Bash on Windows rewrites container paths.**
This is a real trap. In Git Bash / MSYS,

```bash
docker compose exec -T app flask --app run.py demo install --deliverables /data/deliverables
```

becomes `C:/Program Files/Git/data/deliverables` inside the container and fails
with `FileNotFoundError`. Three fixes, best first:

1. Omit the argument — it defaults to `FILES_LOCAL_ROOT`, which is already
   `/data/deliverables` in every container:
   `docker compose exec -T app flask --app run.py demo install`
2. Prefix the command with `MSYS_NO_PATHCONV=1`.
3. Use PowerShell, where no translation happens.

**PowerShell flags versus Linux flags.**
`tinymrp.ps1` accepts both spellings, so commands copied from the Linux docs
work:

| Linux | PowerShell |
| --- | --- |
| `./tinymrp.sh backup --include-deliverables` | `.\tinymrp.ps1 backup -IncludeDeliverables` |
| `./tinymrp.sh restore DIR --yes` | `.\tinymrp.ps1 restore DIR -Yes` |
| `./tinymrp.sh uninstall --delete-data --yes` | `.\tinymrp.ps1 uninstall -DeleteData -Yes` |

**PowerShell scripts and non-ASCII characters.**
Windows PowerShell 5.1 reads `.ps1` files as ANSI unless they carry a UTF-8
BOM, so a stray em dash in a script becomes mojibake — one byte of which is a
double quote that terminates a string and produces a baffling parser error.
Every script shipped here is pure ASCII; keep any you add that way too.

**Docker Desktop file sharing.**
The drive holding the deliverables folder must be listed under
**Settings → Resources → File Sharing**, or the bind mount fails at start.

---

## Operations

**What must a backup contain?**
Three things, or a restore cannot produce a working instance: the database, the
**configuration** (`SECRET_KEY`, `SECURITY_PASSWORD_SALT`, database
credentials), and the deliverables. `./tinymrp.sh backup` captures the first two
and verifies the dump; add `--include-deliverables` for the third.

**How often?**
The database is a few MB compressed — nightly at least. Deliverables are large
and often covered by another backup already; weekly is usually enough.

**Does `uninstall` delete my data?**
No. It removes containers and leaves the Mongo volume, configuration, backups
and deliverables. Only `uninstall --delete-data --yes` removes the Docker
volumes, and even then never your deliverables folder or backups.

**How do updates roll back?**
`./tinymrp.sh update vX.Y.Z` takes a verified backup, swaps the image, and
restores the previous image reference automatically if the new container does
not become healthy. `latest` is rejected — an unpinned tag makes "what is
running" and "roll back one" unanswerable.

**How do I move to another host?**
Backup including deliverables, install the **same version** on the new host,
restore, copy `SECRET_KEY` / `SECURITY_PASSWORD_SALT` / database credentials
across, update `TINYMRP_URL` if the address changed, then verify. Move first,
upgrade after — not both at once.

**What should I monitor?**
`/api/ready`, not `/api/health`. Health returns ok whenever the process is up,
including with an unreachable database or an unmounted volume. Readiness checks
Mongo and free disk. Also watch disk on the deliverables volume, backup age and
size, and `SECURITY:` lines in the log.

**Can I ship logs to a collector?**
`LOG_FORMAT=json` gives one JSON object per line, each carrying the request id.

---

## Security posture

**What does the hardened container actually enforce?** Verified on a running
install: read-only root filesystem, all Linux capabilities dropped,
`no-new-privileges`, and no host ports published for MongoDB or Redis.

**"MongoDB has NO AUTHENTICATION" in the log.**
The Community installer always configures a scoped Mongo user, so you will not
see this there. The source-build compose leaves auth opt-in for backward
compatibility — set `MONGO_ROOT_USER`/`MONGO_ROOT_PASSWORD` and
`MONGO_APP_USER`/`MONGO_APP_PASSWORD` **before first start**, because Mongo
creates users only while initialising an empty data directory. For an existing
volume see `deploy/scripts/enable-mongo-auth.sh`. Set
`TINYMRP_REQUIRE_MONGO_AUTH=true` afterwards so a regression cannot pass
silently.

**Are rate limits real?**
Only with shared storage. With the default `memory://`, every gunicorn worker
keeps its own counters and the effective limit is multiplied by the worker
count. All container stacks point at Redis already. A single-process Waitress
service on Windows does not need it.

**Who can see what?**
Ten canonical roles, reconciled on every start. `customer` and `supplier` are
external portal roles limited to their linked records and released revisions —
that boundary applies even when the user also holds an internal role. See
[06 — First run](06-first-run.md#the-standard-roles).

**Two-factor authentication?**
Optional TOTP: `SECURITY_TWO_FACTOR_ENABLED=true` plus `SECURITY_TOTP_SECRETS`.
`SECURITY_TWO_FACTOR_REQUIRED=true` makes it mandatory.

**Session lifetime?**
30 minutes of inactivity, sliding. "Remember me" extends to
`REMEMBER_COOKIE_DAYS` (7). Cookies are always `HttpOnly` and `SameSite=Strict`.

---

## SolidWorks add-in

**What URL do I give it?**
Exactly your `TINYMRP_URL`, scheme and port included.

**How does it authenticate?**
An API bearer token from **Account → API tokens**, not a session. Tokens expire
after `API_TOKEN_DEFAULT_TTL_DAYS` (90) and cannot exceed
`API_TOKEN_MAX_TTL_DAYS` (365).

**It gets 403 on one action.**
The token carries the user's permissions and the error names the missing one
(`Missing permission: parts.write`). Give the add-in account the narrowest role
that works — normally `engineering`.

**It gets 401 `token_required`.**
No token, or a revoked one. Changing a user's password or roles revokes their
tokens by design; issue a new one.

**Does CORS need configuring for the add-in?**
No. It is a desktop client sending no `Origin`, so CORS never applies.
