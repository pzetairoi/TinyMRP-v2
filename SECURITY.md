# Security Policy

## Reporting

If you discover a security issue, please contact the project owner privately. Provide:
- A clear description of the issue and impact.
- Steps to reproduce.
- Any proposed fix or mitigation.

## Threat Model (high-level)

TinyMRP stores sensitive design data and must protect:
- Authentication tokens and session cookies.
- BOM and deliverables (including proprietary CAD artifacts).
- Admin operations (user management, settings, imports).

Key risks:
- Cross-origin credential leakage (CORS + cookies).
- CSRF on session-authenticated endpoints.
- Weak or default secrets.
- SSRF via file proxy configuration.
- Oversized uploads or proxy responses (DoS).

## Security Modes

TinyMRP supports two runtime security profiles via:

```
TINYMRP_SECURITY_MODE=compat|strict
```

### compat (default)

- Keeps existing behavior where possible.
- Applies an origin/referer CSRF guard to session-authenticated unsafe requests.
- Adds safer CORS behavior (no wildcard + credentials).
- If `SECRET_KEY` or `SECURITY_PASSWORD_SALT` is missing/weak, a temporary in-memory secret is generated and a warning is logged (sessions/tokens reset on restart).

### strict

- `/api/*` requires Bearer tokens only (no session fallback).
- CORS is disabled unless `TINYMRP_ALLOWED_ORIGINS` is set.
- Cookies are Secure + SameSite=Strict.
- Startup fails if secrets are missing/weak.

## Phase 1 Controls (rate limits, token expiry, 2FA, logging)

- **Rate limiting** — on by default. Login and password endpoints: `RATE_LIMIT_LOGIN`
  (default `10 per minute;100 per hour`). Optional global API budget: `RATE_LIMIT_API`.
  With more than one gunicorn worker or multiple instances, set
  `RATE_LIMIT_STORAGE_URI=redis://...` so all workers share one budget (with the default
  in-memory storage each worker counts separately). Throttled requests are audit-logged
  as `security.rate_limited`.
- **File link expiry** — tokenized file URLs expire after `FILES_TOKEN_TTL_SECONDS`
  (default 24 h). The UI generates fresh tokens on every page load, so normal use is
  unaffected; only saved/bookmarked raw links expire. For a migration window you may set
  `FILES_ALLOW_LEGACY_TOKENS=true` to keep accepting pre-expiry tokens — turn it off after.
- **Two-factor (TOTP)** — enable with `SECURITY_TWO_FACTOR_ENABLED=true` plus
  `SECURITY_TOTP_SECRETS` (a stable random secret; generate with
  `python -c "from passlib import totp; print(totp.generate_secret())"`).
  `SECURITY_TWO_FACTOR_REQUIRED=true` enforces it for all users. In strict mode, enabling
  2FA without a TOTP secret refuses to start.
- **Logging** — `LOG_FORMAT=json` emits JSON lines with request IDs for aggregation.
  Every response carries `X-Request-ID` (inbound proxy header honored).

## Incident Response Notes

If you suspect compromise:
1. Rotate `SECRET_KEY` and `SECURITY_PASSWORD_SALT`.
2. Revoke API tokens (or clear `api_tokens` collection).
3. Invalidate sessions by restarting the app after secret rotation.
4. Review audit logs for suspicious actions.
5. Verify proxy upstream and file roots are correct.

See `MIGRATION.md` for a strict-mode rollout checklist.
