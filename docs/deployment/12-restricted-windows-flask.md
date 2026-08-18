# 12 — Windows, restricted environment, `python run.py`

For a locked-down Windows host where `python.exe run.py` is the one command
that has been approved: no Docker, no new Windows service, no new executable,
no elevation. Users reach it by an internal DNS name such as
`http://tinymrp.local:5555`.

This is the variant most likely to break on an upgrade, because it has no
installer writing the configuration for it. Everything below is designed so
that after the first setup you never edit a tracked file again — which is what
makes `git pull` safe.

- [Will my existing instance break? Read this first](#will-my-existing-instance-break-read-this-first)
- [What you run](#what-you-run)
- [Step 1 — Preflight](#step-1--preflight)
- [Step 2 — The environment file](#step-2--the-environment-file)
- [Step 3 — Start it](#step-3--start-it)
- [Step 4 — Administrator and sample data](#step-4--administrator-and-sample-data)
- [Step 5 — Let other machines in](#step-5--let-other-machines-in)
- [Step 6 — Start automatically](#step-6--start-automatically)
- [Updating an existing instance](#updating-an-existing-instance)
- [Every setting run.py reads](#every-setting-runpy-reads)
- [Security of this variant](#security-of-this-variant)
- [Copy-paste command sheet](#copy-paste-command-sheet)

---

## Will my existing instance break? Read this first

If your instance is on a build from before this change and serves
`http://tinymrp.local:5555`, there are **three** things that will bite, and two
of them stop it working completely. All three were reproduced against a copy of
exactly this setup.

### 1. Login returns to the login page — `TINYMRP_URL` missing

**Symptom.** Credentials are accepted, the browser goes straight back to the
login form, or shows:

```
CSRF Error — CSRF session token is missing.
```

**Cause.** With no `TINYMRP_URL`, TinyMRP assumes HTTPS. It marks the session
cookie `Secure`, and a browser refuses to store a `Secure` cookie on a
plain-HTTP origin — so the CSRF token minted with the login form is gone before
the form is posted. `tinymrp.local` is not loopback, so it gets none of the
exemptions that make `http://localhost` work.

**Fix.** One line in your env file:

```bash
TINYMRP_URL=http://tinymrp.local:5555
```

**Verify.** The startup log must say:

```
Browser transport: plain HTTP (TINYMRP_URL=http://tinymrp.local:5555)
```

### 2. The page loads unstyled — same cause, second symptom

The CSP `upgrade-insecure-requests` directive rewrites every script and
stylesheet to `https://` on a port that speaks HTTP, so nothing loads. The same
one-line fix removes it.

### 3. It refuses to start — secrets are now mandatory

**Symptom.**

```
RuntimeError: SECRET_KEY must be set to a strong value.
```

**Cause.** Older builds generated `SECRET_KEY` and `SECURITY_PASSWORD_SALT`
into `instance\` when they were missing. That is gone: an application that
invents its own signing key cannot tell a forged session from a real one after
a restart.

**Fix.** Put both in your env file, 32+ characters each, different from one
another:

```powershell
powershell -c "[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')"
```

> If you already had them in the env file, nothing changes. If they were being
> generated into `instance\runtime_secrets.json`, **copy the values out of that
> file into your env file before restarting** — a fresh pair signs everyone out
> and invalidates every issued file link. A *different*
> `SECURITY_PASSWORD_SALT` invalidates every stored password, so that one
> matters most.

### And one thing that is no longer a problem

If you had **edited `run.py`** locally to change the host or port, you can
delete that edit. `run.py` now takes both from the environment, so it no longer
conflicts on `git pull`. That local edit is a likely part of why the last
update was painful.

---

## What you run

Three files, none of which need elevation:

| File | What it is |
| --- | --- |
| `deploy\windows-restricted\.env.restricted.example` | The env template. Copy it once, edit four values. |
| `deploy\windows-restricted\start-tinymrp.cmd` | Starts the server. Plain batch, so it works where PowerShell scripts are blocked. |
| `deploy\windows-restricted\check-restricted-install.ps1` | Read-only diagnosis of all eight things that can be wrong. Run it before the first start and after every update. |

---

## Step 1 — Preflight

```powershell
cd C:\TinyMRP\app\tinymrp_v2
powershell -ExecutionPolicy Bypass -File .\deploy\windows-restricted\check-restricted-install.ps1
```

It checks Python and the packages, the env file, MongoDB, the deliverables
folder, the port, the firewall and network profile, DNS, and — once the server
is up — whether the session cookie and CSP are actually correct for plain HTTP.
Every failure prints the command that fixes it.

If Python or the virtualenv are missing:

```powershell
cd C:\TinyMRP\app\tinymrp_v2
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Node.js is **not** needed: the compiled frontend is committed.

---

## Step 2 — The environment file

```powershell
New-Item -ItemType Directory -Force -Path C:\TinyMRP\config | Out-Null
Copy-Item .\deploy\windows-restricted\.env.restricted.example C:\TinyMRP\config\.env.lan
notepad C:\TinyMRP\config\.env.lan
```

Four values are marked `REQUIRED`:

```bash
TINYMRP_URL=http://tinymrp.local:5555
FILES_LOCAL_ROOT=C:/TinyMRP/data/deliverables
SECRET_KEY=<32+ random characters>
SECURITY_PASSWORD_SALT=<a different 32+ random characters>
```

Restrict the folder, because it holds your secrets:

```powershell
icacls C:\TinyMRP\config /inheritance:r /grant "Administrators:(OI)(CI)F" /grant "SYSTEM:(OI)(CI)F" /grant "$env:USERNAME:(OI)(CI)R"
```

`TINYMRP_URL` is the only address you configure. `run.py` derives the listening
port from it, and binds `0.0.0.0` because the host in it is not loopback — so
the address users type and the socket the server opens cannot drift apart.

---

## Step 3 — Start it

```cmd
deploy\windows-restricted\start-tinymrp.cmd
```

or with an explicit env file:

```cmd
deploy\windows-restricted\start-tinymrp.cmd C:\TinyMRP\config\.env.lan
```

Equivalent by hand, if you would rather not use the script:

```cmd
cd /d C:\TinyMRP\app\tinymrp_v2
set ENV_FILE=C:\TinyMRP\config\.env.lan
.venv\Scripts\python.exe run.py
```

A correct start prints:

```
Browser transport: plain HTTP (TINYMRP_URL=http://tinymrp.local:5555)
SECURITY: TinyMRP is serving http://tinymrp.local:5555 without TLS, ...
TinyMRP listening on 0.0.0.0:5555 (waitress, debug=off)
Users should open: http://tinymrp.local:5555
```

The `SECURITY:` line is expected on a plain-HTTP LAN deployment. It is a
statement of fact, not a failure.

**Why waitress and not the Flask development server?** Waitress is a pure
Python package already in `requirements.txt`. It runs *inside the same
`python.exe`*, so it needs no separately approved executable — the thing that
usually blocks a proper server on a locked-down host. It handles concurrent
users properly, where the development server is single-purpose and explicitly
not for shared use. `run.py` picks it automatically when it is importable and
falls back to Flask when it is not. Force either with `TINYMRP_SERVER`.

---

## Step 4 — Administrator and sample data

```cmd
cd /d C:\TinyMRP\app\tinymrp_v2
set ENV_FILE=C:\TinyMRP\config\.env.lan
.venv\Scripts\python.exe -m flask --app run.py user seed-roles
.venv\Scripts\python.exe -m flask --app run.py user bootstrap-admin --email admin@company.com
```

`bootstrap-admin` prompts twice without echoing, so the password never reaches
your command history. Minimum 12 characters.

Optional evaluation dataset — 494 sample files, the CV03 assembly and its BOM,
and one login per role so the install can be exercised before real data:

```cmd
.venv\Scripts\python.exe -m flask --app run.py demo install
```

Passwords print once. Remove them before real data arrives:

```cmd
.venv\Scripts\python.exe -m flask --app run.py demo remove --disable
```

See [06 — First run](06-first-run.md) for the roles and what the dataset
contains.

---

## Step 5 — Let other machines in

Three separate things must all be true. The preflight checks all three.

**a) The server listens on the network.** `run.py` binds `0.0.0.0` when
`TINYMRP_URL` names a non-loopback host. Confirm:

```powershell
netstat -an | findstr :5555
```

Must show `0.0.0.0:5555`, not `127.0.0.1:5555`.

**b) The firewall allows the port.** Needs elevation, so this may be an IT
ticket — [`deploy/windows/IT_REQUEST_TEMPLATE.md`](../../deploy/windows/IT_REQUEST_TEMPLATE.md)
is written for that:

```powershell
New-NetFirewallRule -DisplayName "TinyMRP (5555)" -Direction Inbound -Action Allow `
  -Protocol TCP -LocalPort 5555 -Profile Domain,Private -RemoteAddress 192.168.0.0/24
```

> **The trap.** Windows applies a rule only on the profile(s) it is scoped to,
> and warns about nothing when none of them are active. On a network Windows
> has classified **Public**, a `Domain,Private` rule does nothing at all.
> Check with `Get-NetConnectionProfile`; if the network is trusted, reclassify
> it with
> `Set-NetConnectionProfile -InterfaceAlias "<alias>" -NetworkCategory Private`,
> or add `Public` to the rule's `-Profile`.

**c) The name resolves on the clients.** It resolving on the server proves
nothing. Either an internal DNS A record, or per-client:

```powershell
Add-Content C:\Windows\System32\drivers\etc\hosts "`n192.168.0.25`ttinymrp.local"
```

Then from a **different** machine:

```powershell
Test-NetConnection tinymrp.local -Port 5555
curl http://tinymrp.local:5555/api/health
```

Testing from WSL on the same box does not count — that traffic bypasses the
Windows firewall profile rules and succeeds even when a real client is blocked.

---

## Step 6 — Start automatically

`start-tinymrp.cmd` runs in the foreground and stops when the window closes.
For unattended start without installing a service, use Task Scheduler, which
normally needs no special rights for your own account:

```powershell
$action  = New-ScheduledTaskAction -Execute "C:\TinyMRP\app\tinymrp_v2\deploy\windows-restricted\start-tinymrp.cmd" `
                                   -Argument "C:\TinyMRP\config\.env.lan"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
                                         -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName "TinyMRP" -Action $action -Trigger $trigger -Settings $settings `
                       -User "$env:USERDOMAIN\$env:USERNAME" -RunLevel Limited
```

`-AtStartup` needs the task to run whether or not the user is logged on, which
may require a stored password. If that is not permitted, use
`New-ScheduledTaskTrigger -AtLogOn` on a dedicated account that stays signed in.

Where a service is allowed, prefer the service install in
[03 — Windows LAN](03-windows-lan.md#step-7--install-the-tinymrp-service).

---

## Updating an existing instance

```powershell
# 1. Stop it (close the window, or stop the scheduled task)
Stop-ScheduledTask -TaskName "TinyMRP" -ErrorAction SilentlyContinue

# 2. Back up first. All three parts, or a restore will not work.
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
New-Item -ItemType Directory -Force -Path "D:\Backups\TinyMRP\$stamp" | Out-Null
& "C:\Program Files\MongoDB\Tools\100\bin\mongodump.exe" --uri="mongodb://127.0.0.1:27017/tinymrp-v2" `
  --archive="D:\Backups\TinyMRP\$stamp\mongo.archive.gz" --gzip
Copy-Item C:\TinyMRP\config\.env.lan "D:\Backups\TinyMRP\$stamp\env.bak"
Compress-Archive -Path "C:\TinyMRP\data\deliverables\*" -DestinationPath "D:\Backups\TinyMRP\$stamp\deliverables.zip"

# 3. Update the code
cd C:\TinyMRP\app\tinymrp_v2
git status --short          # local edits to run.py are no longer needed - see above
git pull
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 4. Preflight BEFORE starting
powershell -ExecutionPolicy Bypass -File .\deploy\windows-restricted\check-restricted-install.ps1

# 5. Start, then re-run the preflight to see the live cookie and CSP checks pass
deploy\windows-restricted\start-tinymrp.cmd
```

Step 4 is the one that turns a bad upgrade into a five-second fix: it names the
missing `TINYMRP_URL` or `SECRET_KEY` before you discover it through a login
loop.

---

## Every setting `run.py` reads

| Variable | Default | What it does |
| --- | --- | --- |
| `ENV_FILE` | none | Path to the environment file. Values in it override the process environment. |
| `TINYMRP_URL` | unset | The address users type. Drives the cookie/CSP posture **and** the default listening port. |
| `TINYMRP_BIND_HOST` | `0.0.0.0` when `TINYMRP_URL` is non-loopback, else `127.0.0.1` | Interface to listen on. |
| `TINYMRP_BIND_PORT` | port from `TINYMRP_URL`, else `5000` | Port to listen on. |
| `TINYMRP_SERVER` | `waitress` when importable, else `flask` | Which server to run. |
| `TINYMRP_THREADS` | `8` | Waitress worker threads. Raise to 16 for 20+ concurrent users. |
| `TINYMRP_CONNECTION_LIMIT` | `200` | Waitress maximum simultaneous connections. |
| `TINYMRP_CHANNEL_TIMEOUT` | `120` | Seconds before an idle connection is dropped. Raise for very large uploads. |
| `TINYMRP_DEV` | off | Flask debugger and reloader. Refused on a non-loopback bind. |
| `TINYMRP_ALLOW_REMOTE_DEBUG` | off | Override that refusal. Isolated networks only. |

Everything else — database, files, uploads, rate limits, logging — is in
[05 — Configuration reference](05-configuration-reference.md).

---

## Security of this variant

Worth stating plainly, because "restricted environment" and "Flask debug
server" are a contradiction.

| | Status |
| --- | --- |
| Traffic | **Plain HTTP.** Passwords and session cookies cross the network in clear text. Acceptable on a trusted internal network only; never expose this host to the internet. To add TLS see [08](08-networking-and-tls.md#adding-https-to-a-lan-deployment). |
| Debugger | **Off by default now.** `run.py` refuses to combine `TINYMRP_DEV=1` with a network-facing bind. Werkzeug's traceback console executes arbitrary Python in the server process, so a debug server other people can reach is remote code execution behind a friendly error page. If your current instance runs `app.run(debug=True)` bound to the network, that is the most serious problem in this whole document, and it is fixed simply by using the new `run.py`. |
| Database | MongoDB must be `bindIp: 127.0.0.1`. The preflight fails if it is listening on all interfaces. |
| Secrets | In the env file only; never generated, never logged. Restrict the folder ACL. |
| Rate limits | Real here, because there is a single process — in-memory counters are the whole budget. |
| Sessions | `HttpOnly` and `SameSite=Strict` regardless of transport; 30-minute idle timeout. |

---

## Copy-paste command sheet

Everything above, in order, assuming `C:\TinyMRP\app\tinymrp_v2` and
`http://tinymrp.local:5555`.

```powershell
# --- one-time setup -------------------------------------------------
cd C:\TinyMRP\app\tinymrp_v2
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

New-Item -ItemType Directory -Force -Path C:\TinyMRP\config, C:\TinyMRP\data\deliverables | Out-Null
Copy-Item .\deploy\windows-restricted\.env.restricted.example C:\TinyMRP\config\.env.lan
powershell -c "[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')"   # SECRET_KEY
powershell -c "[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')"   # SECURITY_PASSWORD_SALT
notepad C:\TinyMRP\config\.env.lan

powershell -ExecutionPolicy Bypass -File .\deploy\windows-restricted\check-restricted-install.ps1

$env:ENV_FILE = "C:\TinyMRP\config\.env.lan"
.\.venv\Scripts\python.exe -m flask --app run.py user seed-roles
.\.venv\Scripts\python.exe -m flask --app run.py user bootstrap-admin --email admin@company.com
.\.venv\Scripts\python.exe -m flask --app run.py demo install      # optional

# --- every start ----------------------------------------------------
cd C:\TinyMRP\app\tinymrp_v2
.\deploy\windows-restricted\start-tinymrp.cmd C:\TinyMRP\config\.env.lan

# --- after any update -----------------------------------------------
git pull
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File .\deploy\windows-restricted\check-restricted-install.ps1

# --- when something is wrong ----------------------------------------
powershell -ExecutionPolicy Bypass -File .\deploy\windows-restricted\check-restricted-install.ps1
curl http://127.0.0.1:5555/api/ready
```
