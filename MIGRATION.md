# Migration Guide (Security Hardening)

## Safe Path (compat mode, default)

1. `git pull` on the server.
2. Restart services (`docker compose restart` or systemd).
3. Verify the app boots and UI loads.

Compat mode preserves existing behavior, but improves safety:
- CORS is no longer wildcard + credentials.
- Session-authenticated API requests are protected by an origin/referer CSRF guard.
- If `SECRET_KEY`/`SECURITY_PASSWORD_SALT` is missing or weak, a runtime secret is generated once and persisted to `instance/runtime_secrets.json` (sessions/tokens remain stable across restarts). A warning is logged to encourage explicit secrets.

## Enable Strict Mode (opt-in)

Set in your environment:

```
TINYMRP_SECURITY_MODE=strict
SECRET_KEY=<strong secret>
SECURITY_PASSWORD_SALT=<strong salt>
TINYMRP_ALLOWED_ORIGINS=https://your-ui.example.com
```

Optional:

```
TINYMRP_CORS_CREDENTIALS=true   # only if you explicitly need credentialed CORS
FILES_UPSTREAM_ALLOWED_HOSTS=files.example.com
FILES_PROXY_MAX_BYTES=2147483648
```

Strict mode changes:
- `/api/*` requires Bearer tokens (no session cookies).
- CORS disabled unless allowlist is set.
- Secure cookies + SameSite=Strict.
- Startup fails if secrets are missing/weak.

## Admin Seeding Changes

Auto-seeding is now opt-in:

```
TINYMRP_SEED_ADMIN=true
TINYMRP_ADMIN_EMAIL=admin@example.com
TINYMRP_ADMIN_PASSWORD=ChangeMe123!
```

In compat mode, if `TINYMRP_SEED_ADMIN=true` and no password is provided, a one-time password is generated and logged on first boot.

## Secret Rotation Checklist

1. Generate new `SECRET_KEY` and `SECURITY_PASSWORD_SALT`.
2. Update environment and restart services.
3. Revoke/rotate API tokens if needed.
4. Verify login and token-based clients.

## Recovery CLI

```bash
flask --app run.py user list
flask --app run.py role list
flask --app run.py user set-password --email user@example.com
flask --app run.py user bootstrap-admin --email admin@example.com --password ChangeMe123!
```

Docker:

```bash
docker compose exec app flask --app run.py user list
```
