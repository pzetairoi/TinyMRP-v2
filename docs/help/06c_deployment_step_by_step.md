# Deployment: step by step

Pick your situation, run the script, answer the questions. Every variant below
is a numbered sequence you can follow without prior knowledge of TinyMRP, and
every command can be copy-pasted.

The same guides, plus deeper reference material, are in `docs/deployment/` in
the repository, readable on GitHub before anything is installed.

## The only three things you configure

Everything else is generated or has a working default.

| | Setting | Example | Why it matters |
| - | --- | --- | --- |
| 1 | Deliverables folder | `/srv/tinymrp/deliverables`, `C:/TinyMRP/data/deliverables` | Holds `pdf/`, `png/`, `step/`, `edr/`… TinyMRP reads from it and writes thumbnails and uploads into it. |
| 2 | **`TINYMRP_URL`** | `http://192.168.1.50:5000`, `https://tinymrp.example.com` | The address users type, **scheme included**. |
| 3 | Port (optional) | `5000` | Defaults to 5000. If you change it, it must also appear in `TINYMRP_URL`. |

**`TINYMRP_URL` is the setting that decides whether login works at all.** Its
scheme tells TinyMRP whether browsers reach it over TLS:

- `https://` → session cookies are marked `Secure` and the page asks browsers
  to upgrade assets to HTTPS. Correct behind TLS.
- `http://` → neither. Correct on a plain-HTTP network.

Declare `https://` on a plain-HTTP deployment and a browser refuses to store
the session cookie, so every login bounces back to the login page with
*"CSRF session token is missing"* and no explanation. Leave it unset and
TinyMRP assumes HTTPS, which produces the same failure.

None of this shows up on `http://localhost`, because browsers treat loopback as
a trusted origin and exempt it. A LAN address gets no exemption — which is why
a broken configuration can look perfect on the machine it runs on.

## Which variant am I?

| Situation | Guide below | Main script |
| --- | --- | --- |
| Linux VM or server, Docker available | [A](#a-linux-vm-or-server-with-docker) | `deploy/community/install.sh` |
| Windows with Docker Desktop | [B](#b-windows-with-docker-desktop) | `deploy/community/install.ps1` |
| Linux, Docker not permitted | [C](#c-linux-without-docker) | `deploy/scripts/install-server.sh` |
| Windows office LAN, service install | [D](#d-windows-lan-service) | `deploy/windows/install_tinymrp_service.ps1` |
| Windows locked-down host, `python run.py` only | [E](#e-windows-restricted-host-runpy) | `deploy/windows-restricted/start-tinymrp.cmd` |
| Public VPS, several companies | [F](#f-vps-with-several-instances) | `deploy/scripts/create-instance.sh` |

## A. Linux VM or server with Docker

1. Install Docker: `curl -fsSL https://get.docker.com | sudo sh`, then
   `sudo usermod -aG docker "$USER"` and log out and back in.
2. Get the code: `sudo git clone <repo> /opt/tinymrp_v2 && sudo chown -R "$USER":"$USER" /opt/tinymrp_v2`
3. Create the deliverables folder:
   `sudo mkdir -p /srv/tinymrp/deliverables && sudo chown -R 1000:1000 /srv/tinymrp/deliverables`
4. Run the installer:

   ```bash
   cd /opt/tinymrp_v2
   ./deploy/community/install.sh --build --with-demo-data
   ```

5. Answer: deliverables folder, access mode (`localhost`, `lan` or `domain`),
   the address users will type, administrator email and password.
6. Open the URL it prints and sign in.
7. Open the firewall for the port, restricted to your subnet:
   `sudo ufw allow from 192.168.1.0/24 to any port 5000 proto tcp`

Operate it with `./deploy/community/tinymrp.sh status|logs|backup|update|uninstall`.

`--build` builds the image from the checkout, which is what a git clone needs.
`--with-demo-data` loads 494 sample files, a real BOM and one login per role so
the install can be exercised immediately; omit it for a production instance.

## B. Windows with Docker Desktop

1. Install Docker Desktop and start it. Under **Settings → Resources → File
   Sharing**, add the drive holding your deliverables folder.
2. Get the code, then:

   ```powershell
   cd C:\TinyMRP\Server\tinymrp_v2\deploy\community
   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Build -WithDemoData
   ```

3. Answer the same questions as variant A.
4. In `lan` mode, accept the firewall rule when offered — from an elevated
   PowerShell.
5. If other machines cannot reach it, run
   `deploy\windows\check_lan_access.ps1 -Port 5000 -Deployment docker`.

Operate it with `.\tinymrp.ps1 status|logs|backup|update|uninstall`. It accepts
both `-IncludeDeliverables` and `--include-deliverables` styles.

## C. Linux without Docker

MongoDB, gunicorn under systemd, and nginx in front.

```bash
# LAN, plain HTTP
sudo ./deploy/scripts/install-server.sh \
  --http-only --url http://192.168.1.50 \
  --deliverables /srv/tinymrp/deliverables \
  --admin-email admin@yourcompany.com

# Public domain with an automatic certificate
sudo ./deploy/scripts/install-server.sh \
  --domain tinymrp.example.com --certbot \
  --admin-email admin@yourcompany.com --with-fail2ban
```

The installer creates the `tinymrp` service user, the virtualenv, the hardened
systemd unit and the nginx site, generates both secrets, and prints the
one-time administrator password. It is idempotent: re-running it syncs new code
and keeps your `/etc/tinymrp/.env` and certificates.

Node.js is not needed — the compiled frontend is committed.

Then: `sudo systemctl status tinymrp`, `sudo journalctl -u tinymrp -f`.

## D. Windows LAN service

For an office network where a Windows service is permitted. nginx on port 80 is
the only public listener; the app and MongoDB stay on loopback.

1. Install Python 3.12, MongoDB (as a service), and nginx into `C:\nginx`.
2. Confirm MongoDB binds `127.0.0.1` in `mongod.cfg`.
3. Create the virtualenv and install requirements plus waitress.
4. Copy `deploy\windows\.env.windows.lan.example` to
   `C:\TinyMRP\config\.env.lan` and set the four REQUIRED values.
5. Copy `deploy\windows\nginx.lan.conf` to `C:\nginx\conf\nginx.conf`, set
   `server_name` and the deliverables `alias`, then `nginx -t` and start it.
6. Install the service:

   ```powershell
   .\deploy\windows\install_tinymrp_service.ps1 -AppRoot C:\TinyMRP\app\tinymrp_v2 `
     -EnvFile C:\TinyMRP\config\.env.lan -ReplaceExisting
   ```

7. Apply the firewall policy:

   ```powershell
   .\deploy\windows\configure_firewall_lan.ps1 -LanRemoteRanges 192.168.0.0/24 -HttpPort 80
   ```

8. Create the administrator and, optionally, the demo dataset.
9. Verify from another PC, then run `deploy\windows\check_lan_access.ps1` if it
   does not answer.

## E. Windows restricted host (`run.py`)

For a locked-down machine where `python.exe run.py` is the one approved
command: no Docker, no service, no new executable, no elevation. Users reach it
at something like `http://tinymrp.local:5555`.

1. Preflight — it checks Python, the env file, MongoDB, the folder, the port,
   the firewall, DNS, and the live cookie and CSP:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\deploy\windows-restricted\check-restricted-install.ps1
   ```

2. Copy `deploy\windows-restricted\.env.restricted.example` to
   `C:\TinyMRP\config\.env.lan` and set the four REQUIRED values —
   `TINYMRP_URL`, `FILES_LOCAL_ROOT`, and the two secrets.
3. Start it:

   ```cmd
   deploy\windows-restricted\start-tinymrp.cmd C:\TinyMRP\config\.env.lan
   ```

4. Create the administrator:

   ```cmd
   set ENV_FILE=C:\TinyMRP\config\.env.lan
   .venv\Scripts\python.exe -m flask --app run.py user bootstrap-admin --email admin@company.com
   ```

5. Ask IT for an inbound TCP allow rule for your port, scoped to the office
   subnet.
6. Re-run the preflight; it now also checks the live cookie and CSP headers.

`run.py` reads the listening interface and port from `TINYMRP_URL`, so you
never have to edit a tracked file — which is what makes `git pull` safe here.
It uses waitress when available (a pure Python package that runs inside the
same `python.exe`, needing no separately approved executable) and keeps the
Flask debugger off, refusing to combine it with a network-facing bind.

## F. VPS with several instances

One shared Caddy proxy with automatic HTTPS, one isolated instance per company.

```bash
sudo ./deploy/scripts/install-host.sh --acme-email ops@example.com --base-domain example.com
sudo ./deploy/scripts/create-instance.sh company1 company1.example.com
sudo ./deploy/scripts/doctor.sh
```

For an internal VM with no public DNS:

```bash
sudo ./deploy/scripts/create-instance.sh shopfloor shopfloor.test.local --local-mode http
```

Set `WEB_CONCURRENCY` per instance once you pass two on one host.

Nextcloud is **optional** and installed only by the scripts with `nextcloud` in
their name. Skip them and TinyMRP works exactly as documented.

## After any install: first login and sample data

1. Sign in as the administrator the installer created and change the password
   under **Account → Password**.
2. Load the evaluation dataset so the install can be exercised before real data
   arrives:

   ```
   flask --app run.py demo install
   ```

   It copies 494 sample files, seeds the `CV03-TR-A01` assembly with its BOM,
   and creates one login per role scenario. Passwords print once; capture them
   with `> demo-credentials.json`.
3. Work through the acceptance test: health, readiness, login **from another
   machine**, sample data, open a file, expand a BOM, sign in as a demo
   customer and confirm it sees only its own parts, import a small pack,
   restart, take a backup.
4. Remove the demo accounts before real data:
   `flask --app run.py demo remove --disable`

## Every deployment script and its options

Generated from the scripts themselves, so it cannot drift from what they
actually accept. Run any of them with `--help` or `Get-Help` for full detail.

{{AUTO_DEPLOY_SCRIPTS}}

## Every configuration variable

Collected from the shipped `.env*.example` templates.

{{AUTO_ENV_VARS}}

## When something is wrong

| Symptom | Cause | Fix |
| --- | --- | --- |
| Login returns to the login page | `TINYMRP_URL` scheme does not match how you browse | Set it to the exact address users type, including scheme and port; restart |
| Page loads unstyled | Same cause; the CSP is upgrading assets to https | Same fix |
| `SECRET_KEY must be set to a strong value` | Secrets are mandatory and never generated | Put 32+ random characters in the env file |
| `existing-users-skip` and no administrator | Seeding only runs on an empty user collection | `flask user bootstrap-admin --email <address>` |
| HTTP 413 on upload | Three separate caps | Raise `UPLOAD_PACK_MAX_ZIP_MB`, `TINYMRP_MAX_CONTENT_MB`, and the proxy body limit |
| Deliverables not writable | Container runs as uid 1000 | `sudo chown -R 1000:1000 <folder>` |
| Reachable locally, not from other machines | Binding, firewall profile, or DNS | Run the `check_lan_access.ps1` / `check-restricted-install.ps1` diagnostic |
| Sample parts show but no drawing opens | Records written by an older build pointed outside the storage root | Re-run `flask demo install`; it repairs them |

Two endpoints answer without credentials: `/api/health` (the process is alive)
and `/api/ready` (database reachable and disk has room). Alert on the second.
