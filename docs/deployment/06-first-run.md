# 06 — First run: administrator, roles, and sample data

What exists in a brand-new TinyMRP instance, how to sign in, and how to load a
dataset so the install can be exercised before any real data is imported.

- [What a fresh install contains](#what-a-fresh-install-contains)
- [The first administrator](#the-first-administrator)
- [The standard roles](#the-standard-roles)
- [Loading the evaluation dataset](#loading-the-evaluation-dataset)
- [What the dataset gives you](#what-the-dataset-gives-you)
- [Removing the demo accounts](#removing-the-demo-accounts)
- [Creating real users](#creating-real-users)
- [Connecting the SolidWorks add-in](#connecting-the-solidworks-add-in)
- [A five-minute acceptance test](#a-five-minute-acceptance-test)
- [Command reference](#command-reference)

---

## What a fresh install contains

Every start reconciles the ten canonical roles into the database, whether or
not you seed anything else. So a new instance has:

- the ten standard roles, with their exact permission sets;
- one administrator account, if the installer seeded one;
- no parts, BOMs, jobs, orders, customers or suppliers;
- an empty deliverables tree with the expected subfolders created.

Role reconciliation is idempotent and never touches user assignments. If
someone has edited a standard role, the drift is reported rather than silently
overwritten:

```bash
flask user seed-roles --dry-run      # report missing and drifted roles
flask user seed-roles --apply        # restore canonical definitions
```

---

## The first administrator

### Created by the installer

The guided installers ask for an address and password, create the account
before the app starts serving, and then **erase the password from the
configuration file**. Check that it worked:

```bash
# container stacks
docker compose --env-file .env -f compose.yaml exec -T app \
  flask --app run.py user list

# bare metal
sudo -u tinymrp /opt/tinymrp_venv/bin/flask --app app user list
```

Change the password from **Account → Password** at first login.

### Creating one by hand

If seeding was off, or the password was lost:

```bash
flask --app run.py user bootstrap-admin --email admin@yourcompany.com
```

It prompts for the password twice, never echoes it, creates the account if
needed, grants the `administrator` role, and revokes every existing session and
API token for that user.

Constraints: 12+ characters (`SECURITY_PASSWORD_LENGTH_MIN`), not equal to the
email address, and not the known example password `ChangeMe123!`, which is
refused outright.

### The seeding rules

`TINYMRP_SEED_ADMIN=true` creates the first administrator **only when the user
collection is completely empty**. With any user present it reports
`existing-users-skip` and changes nothing — no password reset, no role change.
That is what makes it safe to leave enabled in a persisted environment file
across restarts and updates.

Both `TINYMRP_ADMIN_EMAIL` and `TINYMRP_ADMIN_PASSWORD` are required when it is
on. The container refuses to start rather than invent or log a password:

```
[bootstrap] configuration error: TINYMRP_ADMIN_PASSWORD is required when seeding
[entrypoint] Bootstrap configuration is invalid; refusing to launch.
```

---

## The standard roles

| Slug | Name | Scope |
| --- | --- | --- |
| `administrator` | Administrator | Everything: business, security, system, imports with approved-data override, exports, archive and purge. |
| `security_administrator` | Security Administrator | Users, roles, assignments, token revocation, audit. No business or system-maintenance authority. |
| `engineering_manager` | Engineering Manager | Engineering data with review approval, moderation and approved-data import override. No purge, no commercial. |
| `engineering` | Engineering | Parts, BOMs, files, shares, exports, part-number allocation, low-risk imports. No scheme management, no override, no purge. |
| `commercial` | Commercial (Sales & Procurement) | Purchase and sales orders, customers and suppliers with financials, job planning. No engineering mutation, no portal-user admin. |
| `internal` | Internal (Other Department) | Reads released internal business data, comments, pulls documentation. No financials, no unreleased engineering data, no mutation. |
| `workshop` | Workshop | Job stages, material issue, released part documentation, comments, drawing markups. No commercial or engineering authority. |
| `customer` | Customer | **External portal.** Only linked-customer jobs, sales orders and exact released revisions, with scoped drawing review. |
| `supplier` | Supplier | **External portal.** Only linked-supplier POs, related job context, each PO line's released subtree, with scoped drawing review. |
| `auditor` | Auditor | Broad read-only across audit, configuration, financials, business and unreleased data. No export, mutation, approval or purge. |

Roles are additive: a user with two roles holds the union of their permissions,
except that the `customer` and `supplier` portal boundaries still apply and
strip anything outside the linked relationship.

Create your own roles at **Admin → Roles → New role**. The standard ten are
reconciled on every start, so give custom roles their own names rather than
editing a standard one.

---

## Loading the evaluation dataset

One command makes a fresh install testable end to end:

```bash
# container stacks (from deploy/community/)
docker compose --env-file .env -f compose.yaml exec -T app \
  flask --app run.py demo install

# bare metal
sudo -u tinymrp ENV_FILE=/etc/tinymrp/.env \
  /opt/tinymrp_venv/bin/flask --app app demo install

# Windows LAN service host
$env:ENV_FILE = "C:\TinyMRP\config\.env.lan"
.\.venv\Scripts\flask.exe --app run.py demo install

# development
ENV_FILE=.env.dev flask --app run.py demo install
```

Or pass `--with-demo-data` / `-WithDemoData` to the community installer and it
runs automatically at the end of a fresh install.

It does three things:

1. copies the CV03 sample deliverables into the deliverables root (skipping any
   file that already exists, unless `--overwrite-files`);
2. enables the permission-test environment, so the demo controls appear in
   **Admin → Roles** as well;
3. creates one login per role scenario with the matching parts, BOM,
   customers, suppliers, jobs and orders, and prints the passwords as JSON.

```bash
flask --app run.py demo install > demo-credentials.json
```

The JSON goes to stdout and the "delete these before real data" reminder to
stderr, so redirecting gives you a clean credentials file.

Options:

| Option | Default | Meaning |
| --- | --- | --- |
| `--deliverables PATH` | `FILES_LOCAL_ROOT` | Where to copy the sample files. |
| `--domain DOMAIN` | `demo.com` | Email domain for the demo logins. |
| `--overwrite-files` | off | Replace sample files that already exist. |

Re-running is safe. Files already present are skipped, records are updated in
place, and the demo passwords are **rotated** — the previous set stops working,
so keep the newest output.

> These are real logins with real permissions. Install them on evaluation,
> staging and disposable instances. Remove them before an instance holds
> production data.

---

## What the dataset gives you

**Sample engineering data** — the `CV03-TR-A01` revision A assembly:

| | |
| --- | --- |
| Managed files | 494, about 135 MB |
| Formats | `png` (120), `edr` (81), `thumbs` (81), `3mf` (52), `ply` (52), `step` (52), `pdf` (29), `dxf` (26) |
| BOM | A real multi-level import pack |
| Release states | Released by *TinyManager*, except `CV03-F02` rev B and `ADR-LED-IND`, deliberately held unreleased so scope rules are visible |

**Demo logins** — `permtest.<scenario>@demo.com`, one per role scenario, plus
deliberate combinations that exercise the boundaries:

| Scenario | Roles | Demonstrates |
| --- | --- | --- |
| `administrator` … `auditor` | one standard role each | The baseline of each role |
| `engineering_commercial` | engineering + commercial | Additive internal roles |
| `commercial_supplier` | commercial + supplier | An internal role narrowed by a portal boundary |
| `security_customer` | security admin + customer | The portal boundary beating an administrative role |
| `customer_unreleased` | auditor + customer | Portal scope still hides unreleased data from a role that can otherwise see it |
| `supplier_unreleased` | engineering + supplier | The same in the other direction |
| `customer_spares`, `supplier_running_gear`, `supplier_electrical`, `supplier_finish` | scoped portal users | Different linked relationships seeing different subtrees |

**Business records** — demo customers, suppliers, jobs and purchase orders,
linked to those users so the scoping rules have something to scope.

The last four rows are the point of the dataset: they are how you verify that a
customer login cannot see another customer's parts before you trust the
instance with real ones.

---

## Removing the demo accounts

```bash
flask --app run.py demo remove --disable
```

Deletes every `permtest.*@demo.com` user, their settings, tokens and sessions,
and the `DEMO-*` business records. `--disable` also hides the demo controls in
the admin UI.

Sample **files** are left in the deliverables root on purpose: by the time you
run this they may have been imported, annotated or linked. Delete them by hand
if you want them gone.

---

## Creating real users

### In the UI

**Admin → Users → New user**, then assign roles. External `customer` and
`supplier` users must also be linked to their customer or supplier record —
without the link the portal shows nothing, which is the correct fail-closed
behaviour and a common "why is it empty" support question.

### On the command line

```bash
flask --app run.py user create --email jane@yourcompany.com
flask --app run.py user grant-role --email jane@yourcompany.com --role engineering
flask --app run.py user list
flask --app run.py user revoke-role --email jane@yourcompany.com --role engineering
flask --app run.py user set-password --email jane@yourcompany.com
flask --app run.py user grant-admin --email jane@yourcompany.com
```

Changing a password or a role assignment signs that user out everywhere and
revokes their API tokens, so a permission change takes effect immediately
rather than at their next login.

---

## Connecting the SolidWorks add-in

The add-in authenticates with an API bearer token, not a session cookie.

1. Sign in as the engineering user the add-in will act as.
2. **Account → API tokens → New token**. Copy it — it is shown once.
3. In the add-in settings, set the backend URL to exactly your `TINYMRP_URL`
   and paste the token.

Tokens expire after `API_TOKEN_DEFAULT_TTL_DAYS` (90) and cannot be issued for
longer than `API_TOKEN_MAX_TTL_DAYS` (365). Because tokens carry the user's
permissions, give the add-in account the narrowest role that works — normally
`engineering`.

If the server uses a self-signed certificate, the add-in machine must trust it
or the connection is refused. See
[08 — Networking and TLS](08-networking-and-tls.md#adding-https-to-a-lan-deployment).

Add-in installation itself is covered in
[docs/help/03_addin_installation.md](../help/03_addin_installation.md).

---

## A five-minute acceptance test

Run this on any new instance before handing it over.

1. **Health** — `curl http://<host>:<port>/api/health` returns `ok: true`.
2. **Readiness** — `/api/ready` returns ok. It checks Mongo and free disk, so
   this is the one that catches an unmounted deliverables volume.
3. **Login** — sign in as the administrator, from *another machine* if this is
   a LAN deployment. Landing back on the login form means the address is
   mis-declared: see
   [07 — Troubleshooting](07-troubleshooting.md#i-log-in-and-land-back-on-the-login-page).
4. **Sample data** — run `demo install`, open **Parts**, find `CV03-TR-A01`.
5. **Files** — open the part, check the thumbnail renders and the PDF opens.
   Failures here are almost always deliverables-folder permissions.
6. **BOM** — open the BOM tree and expand to a leaf part.
7. **Scoping** — sign in as `permtest.customer_spares@demo.com` in a private
   window. It must see only its own linked job and released revisions, and
   must not see `CV03-F02` rev B.
8. **Upload** — import a small pack as the administrator and confirm the parts
   appear.
9. **Restart** — restart the service or stack and confirm you are still signed
   in and the data survived.
10. **Backup** — take one backup and confirm it is non-empty.

---

## Command reference

Prefix per deployment:

| Deployment | Prefix |
| --- | --- |
| Container stack | `docker compose --env-file .env -f compose.yaml exec -T app flask --app run.py` |
| VPS instance | `docker exec -it tinymrp-<instance>-app flask --app run.py` |
| Bare metal | `sudo -u tinymrp ENV_FILE=/etc/tinymrp/.env /opt/tinymrp_venv/bin/flask --app app` |
| Windows | `$env:ENV_FILE="C:\TinyMRP\config\.env.lan"; .\.venv\Scripts\flask.exe --app run.py` |
| Development | `ENV_FILE=.env.dev flask --app run.py` |

| Command | Purpose |
| --- | --- |
| `user list` | Every user with active flag and roles |
| `user create --email E` | Create a user (prompts for the password) |
| `user bootstrap-admin --email E` | Create or repair the administrator |
| `user set-password --email E` | Reset a password; signs out and revokes tokens |
| `user grant-role --email E --role R` | Assign a role |
| `user revoke-role --email E --role R` | Remove a role |
| `user grant-admin --email E` | Grant `administrator` |
| `user seed-roles [--dry-run|--apply]` | Reconcile the standard roles |
| `role list` | Roles with permission counts |
| `demo install [--deliverables P]` | Install the evaluation dataset and demo logins |
| `demo remove [--disable]` | Delete the demo logins and records |
| `data seed-demo --scale small\|medium\|large` | Generate a synthetic multi-level BOM for load testing |
| `data clear-demo --tag demo` | Delete synthetic data by seed tag |
| `biz seed` | Sample suppliers, customers, a job and a purchase order |
| `files scan-one --pn P --rev R` | Rediscover files for one part |
| `thumbs rebuild-all` | Regenerate every thumbnail |
| `parts rebuild-search-fields` | Rebuild materialised search fields |
| `audit tail --n 20` | Recent audit entries |
| `audit diag` | Database connectivity check |
