# Row-level-scope demo testing

Use the deterministic demo dataset to confirm external customer and supplier
visibility.

## Commands

```bash
flask user seed-roles
flask rlsdemo seed --reset --domain demo.com --password <temporary-password>
flask rlsdemo report --domain demo.com
flask rlsdemo smoke --domain demo.com
pytest -q
```

Generated credentials and tokens are written under `instance/`; remove them
after testing.

## Expected boundaries

- Customer viewers see only their linked customer, jobs and orders.
- Supplier viewers see only their linked supplier and orders; suppliers do not
  receive job access.
- A scoped role without a customer/supplier link sees no scoped business data.
- Internal roles see the demo records allowed by their permissions.
- Direct requests for another organisation's object return `404`.

Run `flask rlsdemo report` to inspect the exact seeded identifiers, then use
`flask rlsdemo smoke` as the repeatable pass/fail check.
