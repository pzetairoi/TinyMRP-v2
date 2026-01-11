# RLS Demo Testing

This guide creates a deterministic demo dataset and prints a visibility report so you can confirm row-level access control (RLS) for external viewers.

## Commands

```bash
flask user seed-roles
flask rlsdemo seed --reset --domain demo.com --password demo1234
flask rlsdemo report --domain demo.com
flask rlsdemo smoke --domain demo.com
pytest -q
```

Notes:
- Tokens are written to `instance/rlsdemo_tokens.json` (delete after use).
- If you omit `--password`, random passwords are printed and written to `instance/rlsdemo_users.csv`.

## Curl Examples

```bash
curl -H "Authorization: Bearer <TOKEN>" http://localhost:5000/api/jobs
curl -H "Authorization: Bearer <TOKEN>" http://localhost:5000/api/orders
curl -i -H "Authorization: Bearer <TOKEN>" http://localhost:5000/api/jobs/DEMO-JOB-O1
```

## What You Should See

Customer A viewer (`custA.viewer@demo.com`)
- Jobs: `DEMO-JOB-A1`
- Orders: `DEMO-SO-A1`, `DEMO-PO-Y1`
- Forbidden job fetch `DEMO-JOB-B1` -> 404

Customer B viewer (`custB.viewer@demo.com`)
- Jobs: `DEMO-JOB-B1`
- Orders: none
- Forbidden job fetch `DEMO-JOB-A1` -> 404

Supplier X viewer (`supX.viewer@demo.com`)
- Orders: `DEMO-PO-X1`
- Jobs: none (suppliers do not access jobs)
- Forbidden order fetch `DEMO-PO-Y1` -> 404

Supplier Y viewer (`supY.viewer@demo.com`)
- Orders: `DEMO-PO-Y1`
- Jobs: none (suppliers do not access jobs)
- Forbidden order fetch `DEMO-PO-X1` -> 404

Misconfigured customer_viewer (`misconfig.custrole@demo.com`)
- Jobs: none
- Orders: none

Internal users (`admin@demo.com`, `planner@demo.com`, `operator@demo.com`)
- Jobs: all demo jobs
- Orders: all demo orders

## Manual Checklist

1) Run `flask rlsdemo seed` and confirm tokens are printed and saved.
2) Run `flask rlsdemo report` and compare the visible job/order lists to the expected values above.
3) Run `flask rlsdemo smoke` and confirm `"ok": true`.
4) Use curl to verify forbidden objects return 404.
