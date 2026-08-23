# Production update entry point

The current, supported backup, update, rollback, restore and uninstall commands
are maintained in
[`docs/deployment/10-operations.md`](deployment/10-operations.md). Use the
section for the installed deployment type; do not follow old phase-by-phase
rollout notes.

## Durable update sequence

1. Confirm the deployment type and current version.
2. Take a verified database/configuration backup and confirm the rollback
   target.
3. Update one low-risk instance first.
4. Check readiness, login and a representative parts/files/doc-pack workflow.
5. Continue the rollout only after the canary is healthy.
6. Retain the previous image/release and backup until verification is complete.

Exact commands and automatic rollback behaviour are in the canonical
[operations guide](deployment/10-operations.md).

## Existing MongoDB volumes

Changing a password in an environment file does not change credentials already
stored in a MongoDB volume. Do not enable authentication on a populated volume
until the database users exist, or the application can be locked out.

For a guided VPS multi-instance installation, take a verified backup and run:

```bash
sudo ./deploy/scripts/enable-mongo-auth.sh <instance> --dry-run
sudo ./deploy/scripts/enable-mongo-auth.sh <instance>
```

The helper creates least-privilege credentials, updates the instance
configuration, restarts it and verifies the result. For other deployment types,
use the matching procedure in the current deployment guide and take a verified
backup first. Diagnose an existing credential mismatch with
[`docs/deployment/07-troubleshooting.md`](deployment/07-troubleshooting.md).
