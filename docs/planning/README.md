# Planning archive — historical, not instructions

**Nothing in this directory is a guide.** These are working plans and reviews
kept as a record of why the codebase looks the way it does. They describe work
that was mostly completed, they were accurate when written, and they have not
been maintained since. Commands, file paths and defaults in them may no longer
match the code.

If you are trying to *do* something, you want one of these instead:

| You want to | Read |
| --- | --- |
| Install or operate TinyMRP | [`docs/deployment/`](../deployment/README.md) |
| Look up a setting | [`docs/deployment/05-configuration-reference.md`](../deployment/05-configuration-reference.md) |
| Understand the security model | [`SECURITY.md`](../../SECURITY.md) and [`docs/security/`](../security/) |
| See what changed and when | [`CHANGELOG.md`](../../CHANGELOG.md) |

## What is here

| File | What it recorded |
| --- | --- |
| `hardeningplan.txt` | The security hardening programme: secrets, CSRF/CORS, token TTLs, container hardening. Completed. |
| `posthardeningplan.txt` | Follow-up work after hardening, including the VPS fleet. Refers to servers by alias; the aliases are decoded in the git-ignored `deploy/fleet.local.md`. |
| `optimizationplan.txt` | Performance work: query shapes, indexes, payload sizes. |
| `postoptimizationplan.txt` | Follow-up work after the optimisation pass. |
| `productionmaturityplan.txt` | The post-1.0 maturity programme: backups, monitoring, release gates. Largely completed. |
| `2026-08-09-production-readiness-review.md` | A point-in-time readiness review. A snapshot of that date, never updated. |
| `serverdeploymentguide.txt` | A superseded single-host deployment script, kept for reference. Use [`docs/deployment/02-linux-bare-metal.md`](../deployment/02-linux-bare-metal.md) instead. |
| `handycommands.txt` | Scratch shell snippets from development. Personal notes, not a supported interface. |

They are kept rather than deleted because the reasoning behind a decision is
often worth more later than the decision itself. Read them as history.
