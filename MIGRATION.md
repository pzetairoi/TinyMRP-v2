# Migration Guide (Security Hardening)

## Safe upgrade path for an existing compat deployment

1. `git pull` on the server.
2. Restart services (`docker compose restart` or systemd).
3. Verify the app boots and UI loads.

Because strict is now the application and production deployment default, set
`TINYMRP_SECURITY_MODE=compat` explicitly before the first upgrade if the
existing site still uses local HTTP or has not completed the checks below.
Existing guided VPS instances retain the mode persisted in their instance
`.env`; updates do not silently rewrite it. New guided Caddy instances use
strict mode.

Compat mode preserves existing behavior, but improves safety:
- CORS is no longer wildcard + credentials.
- Session-authenticated API requests are protected by an origin/referer CSRF guard.
- If `SECRET_KEY`/`SECURITY_PASSWORD_SALT` is missing or weak, a runtime secret is generated once and persisted to `instance/runtime_secrets.json` (sessions/tokens remain stable across restarts). A warning is logged to encourage explicit secrets.

## Move the deployment to strict mode

Set in your environment:

```
TINYMRP_SECURITY_MODE=strict
SECRET_KEY=<strong secret>
SECURITY_PASSWORD_SALT=<strong salt>
# Needed only for a genuinely cross-origin UI/integration:
TINYMRP_ALLOWED_ORIGINS=https://your-ui.example.com
```

Optional:

```
TINYMRP_CORS_CREDENTIALS=true   # only if you explicitly need credentialed CORS
FILES_UPSTREAM_ALLOWED_HOSTS=files.example.com
FILES_PROXY_MAX_BYTES=2147483648
```

Strict mode changes:
- Same-origin browser APIs use the authenticated session and reject bearer-only substitution.
- Session-authenticated unsafe API requests require a same-origin Origin or Referer.
- Integration endpoints accept bearer tokens; `/api/auth/check` requires one.
- Public-share APIs are anonymous only inside the token-scoped `/api/share/part/...` surface.
- `/api/health` remains anonymous for health checks.
- CORS disabled unless allowlist is set.
- Secure cookies + SameSite=Strict.
- Startup fails if secrets are missing/weak.

Before switching an existing site, verify HTTPS and the proxy's forwarded host
and scheme, then test browser login/navigation, one browser write, the add-in's
token check, an active public share, and an expired/revoked token. A 401 JSON
response now includes `error.code`, `error.message`, and `error.details`.

## Admin Seeding Changes

Auto-seeding is now opt-in:

```
TINYMRP_SEED_ADMIN=true
TINYMRP_ADMIN_EMAIL=admin@example.com
TINYMRP_ADMIN_PASSWORD=<unique-strong-password>
```

On an empty database, opted-in seeding requires both explicit credentials and
assigns the canonical `administrator` role. Missing, malformed, weak, or
historical example credentials stop container startup; no password is generated
or written to container logs. If any users already exist, restart and update are
idempotent and do not change their passwords or role assignments.

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
flask --app run.py user bootstrap-admin --email admin@example.com
```

Docker:

```bash
docker compose exec app flask --app run.py user list
```
