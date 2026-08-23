# Upgrade and maintenance guide for developers

This is the durable checklist for future application and dependency upgrades.
It deliberately contains principles and verification gates, not a narrative of
past implementation work.

## Before changing anything

1. Read [`../../CHANGELOG.md`](../../CHANGELOG.md) and the upstream release
   notes for every dependency or platform being changed.
2. Use [`../deployment/10-operations.md`](../deployment/10-operations.md) for
   backup, update, rollback and restore procedures.
3. For runtime, image or CI pins, follow
   [`../security/supply_chain_policy.md`](../security/supply_chain_policy.md).
4. Confirm the rollback target and take a verified backup before a production
   rollout.

## Durable engineering rules

- Keep authentication, authorisation and configuration on one supported path.
- Make data migrations additive and reversible. Fail clearly before removing
  access or data.
- Measure before optimising. Preserve authorisation and file-safety checks even
  when making them cheaper.
- Keep production container and database protections intact across community,
  LAN and hosted deployment variants.
- Treat a backup as valid only after content verification and periodic restore
  drills.
- Make small, single-purpose commits and deploy a canary before a wider rollout.
- Store current instructions in one canonical document and link to it instead
  of copying commands into release notes or plans.

## Required verification

Run the checks appropriate to the change, including at minimum:

```text
python -m pytest -q
cd frontend
npm test
npm run lint
npm run build
```

Deployment and supply-chain changes also require the contract tests, rendered
configuration checks, image scan and health/readiness exercise named in the
relevant policy or deployment guide.

## Production rollout

Use a versioned build, take a verified backup, update one low-risk instance,
check login plus a representative parts/files/doc-pack workflow, then continue
the rollout. Keep the previous image or release available until verification is
complete. The exact commands remain in
[`../deployment/10-operations.md`](../deployment/10-operations.md).
