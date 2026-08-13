# 03 — TinyMRP on Windows, LAN only

Two supported ways to run TinyMRP on Windows for an office or workshop network.
Neither is exposed to the internet.

| | **A. Docker Desktop** *(recommended)* | **B. Native Windows service** |
| --- | --- | --- |
| Install effort | One script | About 30 minutes |
| Components | Containers only | Python, MongoDB, nginx, a service |
| Updates | `.\tinymrp.ps1 update v2.1.0` | git pull + pip install + restart |
| Backups | Built in and verified | Your own script |
| Needs Docker Desktop | Yes | No |
| Acceptance-tested | Yes | Community-supported |

Choose **B** when IT will not allow Docker Desktop, or the machine cannot run
WSL2/Hyper-V.

**Nextcloud is not involved in either.**

---

# A. Docker Desktop

```powershell
cd C:\TinyMRP\Server\tinymrp_v2\deploy\community
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Build -WithDemoData
```

Answer the prompts (deliverables folder, access mode `lan`, the LAN IP,
administrator email and password) and open the URL it prints. Full detail,
including every parameter and the operations commands, is in
[01 — VM / server with Docker → Windows Docker Desktop](01-vm-docker.md#windows-docker-desktop).

Two Windows-specific requirements:

- Docker Desktop → **Settings → Resources → File Sharing** must include the
  drive holding the deliverables folder, or the bind mount fails at start.
- In `lan` mode the installer offers to add a Windows Firewall rule scoped to
  **Private** networks. Accept it from an elevated PowerShell, or add it
  yourself.

The rest of this page covers option B.

---

# B. Native Windows service

- [What you will build](#what-you-will-build)
- [Downloads](#downloads)
- [Step 1 — Install the prerequisites](#step-1--install-the-prerequisites)
- [Step 2 — Lock MongoDB to loopback](#step-2--lock-mongodb-to-loopback)
- [Step 3 — Lay out the folders](#step-3--lay-out-the-folders)
- [Step 4 — Create the virtualenv](#step-4--create-the-virtualenv)
- [Step 5 — Write the configuration](#step-5--write-the-configuration)
- [Step 6 — Configure nginx](#step-6--configure-nginx)
- [Step 7 — Install the TinyMRP service](#step-7--install-the-tinymrp-service)
- [Step 8 — Apply the firewall policy](#step-8--apply-the-firewall-policy)
- [Step 9 — Create the administrator and load sample data](#step-9--create-the-administrator-and-load-sample-data)
- [Step 10 — Test from another PC](#step-10--test-from-another-pc)
- [Running nginx as a service](#running-nginx-as-a-service)
- [Operating it](#operating-it)
- [Updating](#updating)
- [Backups](#backups)
- [Common errors](#common-errors)

---

## What you will build

```
Workstations ── http://tinymrp-lan.company.local ──► nginx (port 80)
                                                       │
                                                       ├─► waitress 127.0.0.1:8000  (TinyMRP)
                                                       └─► MongoDB 127.0.0.1:27017  (private)
```

Only port 80 is reachable from the network. The app port and the database are
loopback-only and blocked at the firewall as well.

---

## Downloads

| | Where | Notes |
| --- | --- | --- |
| Python 3.12 (64-bit) | <https://www.python.org/downloads/windows/> | Tick **Add python.exe to PATH** |
| MongoDB Community Server | <https://www.mongodb.com/try/download/community> | Install **as a Windows service** |
| nginx for Windows (zip) | <https://nginx.org/en/download.html> | Extract to `C:\nginx` |
| Git for Windows *(optional)* | <https://git-scm.com/download/win> | Makes updates one command |

Everything below runs in **PowerShell as Administrator**.

---

## Step 1 — Install the prerequisites

```powershell
py -0p                     # a 3.12 entry must be listed
python --version
Get-Service MongoDB        # must exist
Test-Path C:\nginx\nginx.exe
```

Fix anything that fails before continuing.

---

## Step 2 — Lock MongoDB to loopback

The default Windows install already binds `127.0.0.1`. Confirm it, because a
database open to the LAN is the single worst outcome of this deployment.

```powershell
notepad "C:\Program Files\MongoDB\Server\7.0\bin\mongod.cfg"
```

```yaml
net:
  port: 27017
  bindIp: 127.0.0.1
```

```powershell
Restart-Service MongoDB
Get-NetTCPConnection -LocalPort 27017 -State Listen |
  Select-Object LocalAddress, LocalPort
# LocalAddress must be 127.0.0.1 — never 0.0.0.0
```

---

## Step 3 — Lay out the folders

```powershell
$AppRoot   = "C:\TinyMRP\app\tinymrp_v2"
$DataRoot  = "C:\TinyMRP\data\deliverables"
$ConfigDir = "C:\TinyMRP\config"
$LogDir    = "C:\TinyMRP\logs"
$EnvFile   = "C:\TinyMRP\config\.env.lan"
$HostName  = "tinymrp-lan.company.local"
$LanCIDR   = "192.168.0.0/24"

New-Item -ItemType Directory -Force -Path $DataRoot,$ConfigDir,$LogDir | Out-Null
```

Get the code:

```powershell
New-Item -ItemType Directory -Force -Path C:\TinyMRP\app | Out-Null
git clone https://github.com/<your-org>/tinymrp_v2.git $AppRoot
```

Verify the layout — a wrong `$AppRoot` is the most common failure here:

```powershell
Test-Path "$AppRoot\requirements.txt"
Test-Path "$AppRoot\run.py"
Test-Path "$AppRoot\deploy\windows\install_tinymrp_service.ps1"
# all three must be True
```

Restrict the config folder: it will hold your secrets.

```powershell
icacls $ConfigDir /inheritance:r /grant "Administrators:(OI)(CI)F" /grant "SYSTEM:(OI)(CI)F"
```

---

## Step 4 — Create the virtualenv

```powershell
Set-Location $AppRoot
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt waitress
```

Node.js is not needed — the compiled frontend is committed to the repository.

Verify:

```powershell
.\.venv\Scripts\python.exe -c "import flask, waitress; print('ok')"
Test-Path "$AppRoot\.venv\Scripts\waitress-serve.exe"
```

---

## Step 5 — Write the configuration

```powershell
Copy-Item "$AppRoot\deploy\windows\.env.windows.lan.example" $EnvFile -Force
notepad $EnvFile
```

Four values must change. The template marks them `REQUIRED`:

```bash
# 1. The address users type. INCLUDE THE SCHEME.
TINYMRP_URL=http://tinymrp-lan.company.local

# 2. Where the deliverables live (forward slashes)
FILES_LOCAL_ROOT=C:/TinyMRP/data/deliverables

# 3 and 4. Two DIFFERENT random secrets
SECRET_KEY=...
SECURITY_PASSWORD_SALT=...
```

Generate the secrets:

```powershell
powershell -c "[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')"
powershell -c "[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')"
```

> **`TINYMRP_URL` is the setting that decides whether this deployment works at
> all.** With `http://`, session cookies are storable on a plain-HTTP origin
> and the page does not try to upgrade its assets to TLS. Declare `https://`
> here without actually terminating TLS and every login bounces straight back
> to the login form. See
> [08 — Networking and TLS](08-networking-and-tls.md#why-the-scheme-matters).

It must match `server_name` in nginx and the port nginx listens on. If nginx is
not on port 80, include the port: `http://tinymrp-lan.company.local:8080`.

If users will type the IP instead of a name, use the IP:
`TINYMRP_URL=http://192.168.0.25`.

---

## Step 6 — Configure nginx

```powershell
Copy-Item "$AppRoot\deploy\windows\nginx.lan.conf" "C:\nginx\conf\nginx.conf" -Force
notepad "C:\nginx\conf\nginx.conf"
```

Change two things:

```nginx
server_name tinymrp-lan.company.local;      # must match TINYMRP_URL's host
...
alias C:/TinyMRP/data/deliverables/;        # three places; must match FILES_LOCAL_ROOT
```

Test and start:

```powershell
Set-Location C:\nginx
.\nginx.exe -t          # "syntax is ok" / "test is successful"
.\nginx.exe             # starts detached; no output means success
Get-Process nginx
```

Useful nginx commands:

```powershell
.\nginx.exe -s reload   # after a config change
.\nginx.exe -s quit     # graceful stop
.\nginx.exe -s stop     # immediate stop
Get-Content C:\nginx\logs\error.log -Tail 50
```

---

## Step 7 — Install the TinyMRP service

```powershell
Set-Location $AppRoot
.\deploy\windows\install_tinymrp_service.ps1 `
  -AppRoot $AppRoot `
  -EnvFile $EnvFile `
  -ServiceName "TinyMRP-App" `
  -DisplayName "TinyMRP Application Service" `
  -Threads 8 `
  -ConnectionLimit 400 `
  -ChannelTimeout 120 `
  -ReplaceExisting
```

| Parameter | Default | Meaning |
| --- | --- | --- |
| `-AppRoot` | required | Repository checkout. |
| `-EnvFile` | required | Configuration file. |
| `-ServiceName` | `TinyMRP-App` | Windows service name. |
| `-DisplayName` | `TinyMRP Application Service` | Name in services.msc. |
| `-ServiceUser` | `LocalSystem` | A domain account needs `-ServicePassword` and write access to the deliverables folder. |
| `-Threads` | `8` | Waitress worker threads. Raise to 16 for 20+ concurrent users. |
| `-ConnectionLimit` | `400` | Maximum simultaneous connections. |
| `-ChannelTimeout` | `120` | Seconds before an idle channel is dropped. Raise for very large uploads. |
| `-ReplaceExisting` | off | Delete and recreate an existing service. |

The script registers the service as auto-start and configures automatic restart
after failure (three attempts, 5 s apart).

```powershell
Get-Service TinyMRP-App        # Status must be Running
Invoke-WebRequest http://127.0.0.1:8000/api/health -UseBasicParsing |
  Select-Object -ExpandProperty Content
```

Waitress is single-process, so in-memory rate-limit counters are a real budget
here and Redis is not required.

---

## Step 8 — Apply the firewall policy

```powershell
Set-Location $AppRoot
.\deploy\windows\configure_firewall_lan.ps1 `
  -LanRemoteRanges $LanCIDR `
  -HttpPort 80
```

This replaces any previous rules in the `TinyMRP LAN` group and then:

- allows inbound TCP 80 **only** from the ranges you gave, on the Domain and
  Private profiles;
- blocks inbound TCP 8000 from everywhere;
- blocks inbound TCP 27017 from everywhere.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `-LanRemoteRanges` | `10.0.0.0/8,172.16.0.0/12,192.168.0.0/16` | Allowed source ranges. Narrow this to your subnet. |
| `-HttpPort` | `80` | Port nginx listens on. |
| `-AppPort` | `8000` | Blocked. |
| `-MongoPort` | `27017` | Blocked. |
| `-RuleGroup` | `TinyMRP LAN` | Firewall rule group. |

CIDR notation catches people out: a single PC is `192.168.0.111/32`, a whole
subnet is `192.168.0.0/24`. `192.168.0.111/24` is rejected.

```powershell
Get-NetFirewallRule -Group "TinyMRP LAN" |
  Format-Table DisplayName, Enabled, Direction, Action, Profile
```

---

## Step 9 — Create the administrator and load sample data

```powershell
Set-Location $AppRoot
$env:ENV_FILE = $EnvFile

.\.venv\Scripts\flask.exe --app run.py user seed-roles
.\.venv\Scripts\flask.exe --app run.py user bootstrap-admin --email admin@yourcompany.com
# prompts twice, never echoes; 12+ characters

.\.venv\Scripts\flask.exe --app run.py demo install
```

`demo install` copies the CV03 sample deliverables, seeds one demo login per
role and prints the passwords once. Skip it if this machine is going straight
into production use; see [06 — First run](06-first-run.md).

Confirm:

```powershell
.\.venv\Scripts\flask.exe --app run.py user list
```

---

## Before you blame the network: run the diagnostic

Whichever Windows option you chose, this answers "why can nobody else reach
it?" without guesswork. It is read-only and prints the fix for anything it
finds:

```powershell
.\deploy\windows\check_lan_access.ps1 -Port 80
.\deploy\windows\check_lan_access.ps1 -Port 5000 -Deployment docker
```

It checks the six things that actually cause it:

1. **The network is classified Public.** Windows applies a firewall rule only
   on the profile(s) it is scoped to and warns about nothing when none are
   active, so a Domain/Private rule is completely inert on a Public network.
   This is the most common cause and the least visible.
2. No inbound allow rule for the port.
3. A Block rule winning — Windows evaluates Block before Allow.
4. The service listening on `127.0.0.1` instead of `0.0.0.0`.
5. `TINYMRP_URL` not matching the address users type.
6. The host name not resolving on the clients.

Fixing 1, when the network is one you trust:

```powershell
Get-NetConnectionProfile
Set-NetConnectionProfile -InterfaceAlias "Ethernet" -NetworkCategory Private
```

If you cannot reclassify it, scope the rule to Public as well — it stays
restricted to your subnet either way:

```powershell
.\deploy\windows\configure_firewall_lan.ps1 -LanRemoteRanges 192.168.0.0/24 -IncludePublicProfile
```

> **Docker Desktop behaves differently from the native service here.** Docker
> Desktop ships its own inbound rules for `com.docker.backend`, which are
> commonly scoped Public — so a Docker-published port can stay reachable on a
> Public network where a native nginx listener on the same machine would not
> be. Do not conclude from "the Docker install worked" that the native install
> will.

> **Testing from WSL on the same machine proves nothing.** WSL-to-host traffic
> does not traverse the standard Windows Defender Firewall profile rules, so it
> succeeds even when a real LAN client is blocked. Use a separate device.

---

## Step 10 — Test from another PC

First give the name an address. Either add an `A` record on your DNS server, or
on each workstation:

```powershell
Add-Content C:\Windows\System32\drivers\etc\hosts "`n192.168.0.25`ttinymrp-lan.company.local"
```

Then, from that workstation:

```powershell
Test-NetConnection 192.168.0.25 -Port 80      # TcpTestSucceeded : True
Test-NetConnection 192.168.0.25 -Port 8000    # must be False
Test-NetConnection 192.168.0.25 -Port 27017   # must be False

Invoke-WebRequest http://tinymrp-lan.company.local/api/health -UseBasicParsing
```

Then open `http://tinymrp-lan.company.local` in a browser and sign in.

If login returns you to the login page, check that `TINYMRP_URL` uses `http://`
and names exactly the host you typed:

```powershell
(Invoke-WebRequest http://tinymrp-lan.company.local/login -UseBasicParsing).Headers['Set-Cookie']
# must NOT contain "Secure"
```

Use this URL for the SolidWorks add-in backend setting too.

---

## Running nginx as a service

`nginx.exe` started by hand does not survive a reboot. Register it with
[NSSM](https://nssm.cc/):

```powershell
nssm install TinyMRP-Nginx C:\nginx\nginx.exe
nssm set TinyMRP-Nginx AppDirectory C:\nginx
nssm set TinyMRP-Nginx Start SERVICE_AUTO_START
nssm set TinyMRP-Nginx AppStopMethodConsole 0
nssm set TinyMRP-Nginx AppStdout C:\TinyMRP\logs\nginx-stdout.log
nssm set TinyMRP-Nginx AppStderr C:\TinyMRP\logs\nginx-stderr.log
Start-Service TinyMRP-Nginx
```

Then reboot and confirm both services come back:

```powershell
Get-Service TinyMRP-App, TinyMRP-Nginx, MongoDB
```

---

## Operating it

```powershell
Get-Service TinyMRP-App
Restart-Service TinyMRP-App          # after any change to .env.lan
Stop-Service TinyMRP-App
Start-Service TinyMRP-App

Get-EventLog -LogName Application -Source "TinyMRP*" -Newest 20
Get-Content C:\nginx\logs\error.log -Tail 50 -Wait

Set-Location C:\nginx; .\nginx.exe -t; .\nginx.exe -s reload
```

The service reads `.env.lan` once at start, so a configuration change needs a
restart.

---

## Updating

```powershell
Stop-Service TinyMRP-App

Set-Location $AppRoot
git fetch --tags
git checkout v2.1.0
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Start-Service TinyMRP-App
Invoke-WebRequest http://127.0.0.1:8000/api/health -UseBasicParsing
```

Back up first (below). `.env.lan` lives outside the repository, so a checkout
never touches it.

---

## Backups

```powershell
# C:\TinyMRP\scripts\backup.ps1
$ErrorActionPreference = "Stop"
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$dest  = "D:\Backups\TinyMRP\$stamp"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

& "C:\Program Files\MongoDB\Tools\100\bin\mongodump.exe" `
  --uri="mongodb://127.0.0.1:27017/tinymrp-v2" `
  --archive="$dest\mongo.archive.gz" --gzip

Copy-Item "C:\TinyMRP\config\.env.lan" "$dest\env.bak"   # secrets: keep it safe
Compress-Archive -Path "C:\TinyMRP\data\deliverables\*" `
  -DestinationPath "$dest\deliverables.zip"

Get-ChildItem "D:\Backups\TinyMRP" -Directory |
  Where-Object { $_.CreationTimeUtc -lt (Get-Date).ToUniversalTime().AddDays(-14) } |
  Remove-Item -Recurse -Force
```

```powershell
$action  = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\TinyMRP\scripts\backup.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -TaskName "TinyMRP Backup" -Action $action -Trigger $trigger `
  -User "SYSTEM" -RunLevel Highest
```

All three parts matter. Without `env.bak` the restored database has a different
`SECRET_KEY` (everyone signed out, file links dead) and a different
`SECURITY_PASSWORD_SALT` (**every password invalid**).

Restore:

```powershell
Stop-Service TinyMRP-App
& "C:\Program Files\MongoDB\Tools\100\bin\mongorestore.exe" `
  --uri="mongodb://127.0.0.1:27017" --drop --gzip `
  --archive="D:\Backups\TinyMRP\<stamp>\mongo.archive.gz"
Expand-Archive "D:\Backups\TinyMRP\<stamp>\deliverables.zip" `
  -DestinationPath "C:\TinyMRP\data\deliverables" -Force
Start-Service TinyMRP-App
```

---

## Common errors

| Message or symptom | Cause | Fix |
| --- | --- | --- |
| `Could not open requirements.txt` | Wrong `$AppRoot` | Re-run the three `Test-Path` checks in Step 3 |
| `waitress-serve not found` | Dependencies not installed in `.venv` | Repeat Step 4 |
| `Run this script from an elevated PowerShell session` | Not Administrator | Right-click → Run as administrator |
| `Service 'TinyMRP-App' already exists` | Previous install | Add `-ReplaceExisting` |
| `New-NetFirewallRule: ... invalid address` | Bad CIDR | `/32` for one PC, `/24` for a subnet |
| Service starts then stops immediately | Missing/short secret, or unreachable Mongo | `Get-EventLog -LogName Application -Newest 20`; check both secrets are 16+ characters and differ |
| `bind() to 0.0.0.0:80 failed` | IIS or another service owns port 80 | `Get-NetTCPConnection -LocalPort 80 -State Listen`; stop it (`Stop-Service W3SVC`) or move nginx to 8080 and add the port to `TINYMRP_URL` |
| Login loops back to the login page | `TINYMRP_URL` scheme or host wrong | Must be `http://` and the exact host typed. [Details](07-troubleshooting.md#i-log-in-and-land-back-on-the-login-page) |
| Page loads unstyled | Same cause: the CSP is upgrading assets to https | Same fix |
| Thumbnails missing, uploads fail | Service account cannot write the deliverables folder | Grant the service account Modify on `C:\TinyMRP\data\deliverables` |
| Reachable on the server, not from other PCs | Firewall or `server_name` | Step 8; confirm the name resolves |

More in [07 — Troubleshooting](07-troubleshooting.md). For an IT ticket, there
is a template at
[deploy/windows/IT_REQUEST_TEMPLATE.md](../../deploy/windows/IT_REQUEST_TEMPLATE.md).
