# TinyMRP deployment

Everything you need to stand up TinyMRP, from a laptop evaluation to a
multi-tenant VPS. These pages are written to be read on GitHub before you have
a server: no page assumes you are already logged into one.

## What TinyMRP actually needs

Three things. Everything else has a working default or is generated for you.

| | Setting | Example | Why it matters |
| - | --- | --- | --- |
| 1 | **Where the deliverables live** | `/srv/tinymrp/deliverables`, `C:/TinyMRP/data/deliverables` | The folder holding `pdf/`, `png/`, `step/`, `edr/`, … . TinyMRP reads from it and writes thumbnails and uploads into it. |
| 2 | **The address users type** — `TINYMRP_URL` | `http://192.168.1.50:5000`, `https://tinymrp.example.com` | **Include the scheme.** It is not cosmetic: `http` vs `https` decides whether session cookies are marked `Secure` and whether the page asks browsers to upgrade assets to TLS. Get it wrong and login loops for ever. See [Networking, addresses and TLS](08-networking-and-tls.md). |
| 3 | **The port** *(optional)* | `5000` | Defaults to `5000`. If you change it, it must appear in `TINYMRP_URL` too. |

The guided installers generate the database credentials, the Flask signing
secrets, the first administrator password, and the reverse-proxy configuration.
You are never asked to invent a secret.

## Pick a path

| You have | Use | Guide |
| --- | --- | --- |
| A Linux VM or server, Docker available | **Docker Compose, single instance** — recommended | [01 — VM / server with Docker](01-vm-docker.md) |
| A Linux server, no Docker allowed | systemd + gunicorn + nginx | [02 — Linux bare metal](02-linux-bare-metal.md) |
| A Windows machine on an office LAN | Waitress service + nginx, or Docker Desktop | [03 — Windows LAN](03-windows-lan.md) |
| A locked-down Windows host where only `python run.py` is approved | `run.py` + waitress, no service, no elevation | [12 — Windows restricted](12-restricted-windows-flask.md) |
| A public VPS hosting several companies | Guided Caddy multi-instance with automatic HTTPS | [04 — VPS, multiple instances](04-vps-multi-instance.md) |
| A developer machine | `python run.py` against local MongoDB | [09 — Local development](09-local-development.md) |

## One script per variant

The whole install is a script in every case. These are the entry points; each
guide explains the questions it asks and every option it accepts.

| Variant | Install | Operate | Diagnose |
| --- | --- | --- | --- |
| VM / server with Docker | `deploy/community/install.sh --build --with-demo-data` | `deploy/community/tinymrp.sh` | `curl <url>/api/ready` |
| Windows Docker Desktop | `deploy\community\install.ps1 -Build -WithDemoData` | `deploy\community\tinymrp.ps1` | `deploy\windows\check_lan_access.ps1` |
| Linux bare metal | `deploy/scripts/install-server.sh --url <url> …` | `systemctl … tinymrp` | `journalctl -u tinymrp -f` |
| Windows LAN service | `deploy\windows\install_tinymrp_service.ps1` | `Restart-Service TinyMRP-App` | `deploy\windows\check_lan_access.ps1` |
| Windows restricted | `deploy\windows-restricted\start-tinymrp.cmd` | same script | `deploy\windows-restricted\check-restricted-install.ps1` |
| VPS multi-instance | `deploy/scripts/create-instance.sh <name> <domain>` | `deploy/scripts/update-instance.sh` | `deploy/scripts/doctor.sh` |

The same catalogue, with every option each script accepts, is generated from
the scripts themselves and shown in the application's own help under
**Deployment: step by step → Every deployment script and its options**.

None of these paths require Nextcloud. Nextcloud is an **optional** file-sync
front end for the VPS path only; see
[Nextcloud is optional](04-vps-multi-instance.md#nextcloud-is-optional).

## Then

- [05 — Configuration reference](05-configuration-reference.md) — every
  environment variable, its default, and when to change it.
- [06 — First run: administrator, roles, sample data](06-first-run.md) — how to
  log in, what the standard roles are, and how to load the evaluation dataset
  so a fresh install can be exercised immediately.
- [07 — Troubleshooting](07-troubleshooting.md) — symptoms to causes, starting
  with the login loop.
- [08 — Networking, addresses and TLS](08-networking-and-tls.md) — firewalls,
  reverse proxies, and how to add HTTPS to a LAN deployment.
- [10 — Backups, updates and uninstall](10-operations.md) — the routine
  operational commands for each path.
- [11 — FAQ](11-faq.md) — the questions people actually ask, including
  "other machines cannot reach it" and the Windows/Git Bash gotchas.
- [12 — Windows, restricted environment](12-restricted-windows-flask.md) —
  `python run.py` on a locked-down host, and what breaks when it is upgraded.

## Diagnostics

| Situation | Run |
| --- | --- |
| Other machines cannot reach a Windows host | `deploy\windows\check_lan_access.ps1 -Port <port>` |
| Anything wrong on a multi-instance VPS | `sudo ./deploy/scripts/doctor.sh` |
| Is it alive / is it ready? | `curl <url>/api/health` and `curl <url>/api/ready` |
| What configuration is actually in effect? | **Admin → Diagnostics** (secrets redacted) |

## The 60-second version

On a Linux VM with Docker, from a clone of this repository:

```bash
./deploy/community/install.sh --build --with-demo-data
```

Answer three questions (deliverables folder, access mode + address,
administrator email and password) and open the URL it prints.
