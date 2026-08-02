# TinyMRP — Standalone Linux Server (tier T2: nginx + gunicorn, no containers)

Hardened single-host deployment for production. Two equivalent paths: scripted (recommended)
or manual. Both end with: gunicorn on localhost:8000 (systemd, sandboxed), nginx terminating
TLS with rate limiting and security headers, MongoDB local-only, strict security mode.

## Scripted install (recommended)

```bash
sudo ./deploy/scripts/install-server.sh \
  --domain mrp.example.com \
  --certbot \
  --admin-email admin@example.com \
  --with-fail2ban --yes
```

Certificate variants: `--certbot` (public host, Let's Encrypt), `--self-signed` (lab/VPN),
`--cert <fullchain> --key <privkey>` (internal CA), `--http-only` (LAN pilots only).
Other options: `--deliverables <dir>`, `--mongo-uri <uri>` (external MongoDB), `--compat`,
`--skip-ufw`. Re-running is safe: existing env, certs and data are preserved.

For an empty user database, the script prints a one-time administrator password
at the end; change it after first login. Re-running against an existing user
database does not reset any password or role assignment.

## Manual install (what the script does)

1. Packages: `apt install python3-venv nginx` plus MongoDB Community 7.0 from the official
   repo (`mongod` bound to 127.0.0.1, the default).
2. System user: `useradd --system --shell /usr/sbin/nologin tinymrp`.
3. Code at `/opt/tinymrp_v2` (exclude `.git`, `tests`, `node_modules`), venv at
   `/opt/tinymrp_venv`, `pip install -r requirements.txt`. Everything owned by `tinymrp`.
4. `/etc/tinymrp/.env` (mode `0640`, `root:tinymrp`) — start from `.env.server.example`;
   set strong `SECRET_KEY`/`SECURITY_PASSWORD_SALT` (`openssl rand -base64 48`) and
   `TINYMRP_SECURITY_MODE=strict`.
5. systemd: copy `deploy/tinymrp.service` to `/etc/systemd/system/` (sandboxed unit:
   `ProtectSystem=strict`, `NoNewPrivileges`, syscall filter; only the deliverables dir and
   `instance/` are writable). `systemctl enable --now tinymrp`.
6. nginx:
   - `deploy/server/nginx-http-context.conf` → `/etc/nginx/conf.d/tinymrp-http.conf`
   - `deploy/server/snippets-security-headers.conf` → `/etc/nginx/snippets/tinymrp-headers.conf`
   - `deploy/server/nginx-tinymrp-site.conf` → `/etc/nginx/sites-available/tinymrp`
     (replace the `__PLACEHOLDER__` values), symlink into `sites-enabled`, remove `default`,
     `nginx -t && systemctl reload nginx`.
7. Firewall: `ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw enable`.
8. First admin (password is prompted securely): `cd /opt/tinymrp_v2 && sudo -u tinymrp /opt/tinymrp_venv/bin/flask --app app user bootstrap-admin --email <email>`.
9. Optional fail2ban: install the two files from `deploy/server/fail2ban-*` into
   `/etc/fail2ban/{filter.d,jail.d}/` and restart fail2ban.

## Post-install checks

```bash
systemctl status tinymrp
curl -fsS http://127.0.0.1:8000/api/health          # app direct
curl -fsS https://<domain>/api/health               # through nginx/TLS
sudo nginx -t
sudo fail2ban-client status tinymrp-login            # if installed
# External TLS grade (from another machine): testssl.sh https://<domain>
```

## Updating

```bash
cd /opt/tinymrp_v2 && sudo rsync -a --delete --exclude '.git' <checkout>/ ./
sudo -u tinymrp /opt/tinymrp_venv/bin/pip install -r requirements.txt
sudo systemctl restart tinymrp && curl -fsS http://127.0.0.1:8000/api/health
```

Logs live in journald (`journalctl -u tinymrp`); journald is capped at 1 GB by the installer.
nginx logs rotate via the distro's default logrotate config.
