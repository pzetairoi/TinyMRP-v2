# Security Policy

## Reporting

Please report vulnerabilities privately through
[GitHub Security Advisories](https://github.com/pzetairoi/TinyMRP-v2/security/advisories/new).
Do not open a public issue before the report has been assessed. Include:

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

## Security Model

One model, no alternatives:

- An origin/referer CSRF guard on every session-authenticated unsafe request.
  A request carrying neither header is refused.
- CORS disabled unless an origin is explicitly allowlisted; credentials only
  against that allowlist, never with a wildcard.
- Secure + SameSite=Strict cookies.
- `SECRET_KEY` and `SECURITY_PASSWORD_SALT` must be supplied and strong, or the
  application refuses to start. It never generates its own.

### In detail

- Browser/session APIs require the authenticated same-origin session; bearer tokens cannot substitute for browser access.
- Integration APIs accept bearer tokens, with the token-check endpoint bearer-only.
- Public-share APIs are limited to matched share endpoints and validate the opaque share capability; health remains anonymous.
- Unsafe session-authenticated API requests require a same-origin Origin or Referer.
- CORS is disabled unless `TINYMRP_ALLOWED_ORIGINS` is set.
- Cookies are Secure + SameSite=Strict.
- Startup fails if secrets are missing/weak.

## Operational controls

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
3. Session identities rotate automatically on password, activation and authorization-state changes. Rotate application secrets only for an incident-wide logout.
4. Review audit logs for suspicious actions.
5. Verify proxy upstream and file roots are correct.


