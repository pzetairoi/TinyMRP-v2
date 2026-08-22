# Configuration

This page is for admin users who maintain TinyMRP operations.

## Admin Dashboard (`/admin`)

Main admin modules:

- Users
- Roles
- Audit Log
- Metrics
- Backups
- App Settings
- Add-in Admin
- Jobs, Suppliers, Customers, Orders shortcuts

## App Settings (`/admin/settings`)

### Branding

- Upload PNG or SVG logo used in UI and doc packs.
- Optional remove-logo toggle to return to default.

### Timezone

- Sets timezone used in generated document timestamps.
- Use valid IANA names (example: `America/New_York`).

### Hardware classification

- Folder keywords used to classify hardware during ZIP import.
- Case-insensitive matching.

### Flat pattern page filter

- Sheet-name tokens used to remove flat pattern pages from binder output.

### Upload Pack limits

- Max ZIP size (MB)
- Max file size (MB)
- Max files per ZIP
- `0` disables a limit

## Users And Roles

### Users (`/admin/users`)

- Create, edit, bulk-delete users.
- Optional password reset in user edit.

### Roles (`/admin/roles`)

- Create/edit role permission sets.
- Typical permission groups:
  - Items/BOM
  - Jobs/Orders
  - Suppliers/Customers
  - Tools/Import
  - Numbering management

Do not change access behavior in code unless intentionally redesigning ACL. Production access should be managed through roles, permissions, and entity links.

## Fields And Exports (`/ui/admin/fields`)

Use **Fields & exports** to keep field names, import aliases and visible columns
consistent across the application.

The **Screen & export presets** section is destination-specific. For each
parts table, BOM, summary, where-used or export context:

- **Allowed fields** are the columns a user may choose.
- **Default preset** is what appears after a user resets their personal layout.
- A field marked **required** cannot be removed from that context.

![The Parts table preset showing allowed fields, the default column set and the required Part Number field.](/static/help/img/admin-fields.png)

Open one destination at a time, make the smallest necessary change, then press
**Save** at the top of the page. Changing a default does not erase an existing
user layout; they receive the new default when they choose **Reset**.

## Access Scoping Model (Operational View)

External users can be scoped by linked entities:

- A linked user must also have the matching canonical **Customer** or
  **Supplier** portal role; a company link alone does not create access.
- Customer users see only their customer, jobs, sales orders and contractual
  BOM subtree.
- Supplier users see only their supplier, purchase orders and each PO-line
  subtree. A job vendor link provides context but never the complete job BOM.
- Internal privileged roles remain unscoped.

This scoping is enforced server-side on jobs, orders, customers, suppliers,
parts, comments, markups and related views. Unapproved nodes stop traversal by
default. For a named external reviewer, `parts.read_unreleased` removes that
approval barrier without widening the relationship scope.

## Customer And Supplier Master Data

### Customers (`/admin/customers`)

- Company, contacts, addresses, tags, status/type.
- Linked users list controls customer-scoped access.
- Related jobs and orders are visible in detail view.

### Suppliers (`/admin/suppliers`)

- Company, contact/rating, categories, processes, lead time, tags.
- Linked users list controls supplier-scoped access.
- Related orders visible in detail view.

## Jobs Administration (`/admin/jobs`)

- Manage schedule, status, priority, participants, vendors, customer.
- Edit job BOM with part picker and inline filters.
- Analyze purchasing coverage:
  - Parts in Orders
  - Over-Ordered Parts
  - Parts Not Yet Ordered (Flat/Tree)

## Orders Administration (`/admin/orders`)

- Purchase and sales order lifecycle management.
- Line-level pricing, discount, tax, and summary totals.
- Job-linked orders can lock customer selection.
- Docpack export and scope-of-supply export are available per order.

## Add-in Admin (`/ui/admin/addin`)

- Review users and revoke add-in tokens.
- Manage numbering scheme metadata:
  - preset flag
  - recommended flag
  - quickstart visibility
- Build/validate/save/deactivate schemes in browser.

### The built-in numbering scheme

A new instance starts with one scheme, *Default: PART-SEQ6*, so there is
something to allocate from on day one. It is a starting point, not a fixture:

- **It can be deleted, and it stays deleted.** It is seeded once, into a
  database that has no scheme at all. It is never recreated afterwards — not on
  restart, not on upgrade.
- **You can delete every scheme.** *Start from* in the scheme builder defaults
  to **Blank**, so a new scheme is always available even with nothing to copy.
  Copying an existing scheme is a convenience, never the only route.
- With no scheme at all, nothing can be allocated until you create one. Parts
  imported from CAD are unaffected — they carry the numbers CAD already gave
  them.

### Stopping a scheme at a last number

A scheme's counter can be given an optional **maximum**. Once the counter passes
it, allocation refuses with *“This scheme stops at N; its last number has already
been issued”* and **no part is created** — the run allocates nothing rather than
issuing a number the scheme's own rule forbids.

Leave the maximum at **0** for no limit. That is the default, and it is what
every scheme created before this option existed does, so nothing changes unless
you set one. The maximum cannot be below the counter's start value.

Use it to hand a block of numbers to a project or a supplier and know the block
cannot be overrun. To carry on afterwards, raise the limit or create a second
scheme.

## Upload pack housekeeping

Every *Create upload pack* from the add-in leaves a timestamped ZIP in the
`bom` folder of your deliverables storage. Nothing reads them once the import
has run, so they accumulate — one instance had built up 1,258 of them.

Packs older than **7 days** are moved into `bom/archive`. They are **moved,
never deleted**: the pack is the only record of what an import contained, so
the disk cost is unchanged and only the working folder gets tidier.

The sweep runs after an import, at most once a day, so there is nothing to
schedule or install. Set the retention to **0** to switch it off entirely.

## Backups (`/admin/backups`)

Reached from **Admin → System → Backups**. It reports; it never writes.

- **What gets backed up.** The database is captured daily and is small.
  Deliverables are **off by default** — they are large and can usually be
  regenerated from CAD — and when switched on the page shows how often they are
  copied, roughly what a copy costs, and where it is written.
- **Room left** on the disk holding the backups.
- **What you have**, newest first, each marked *Database + files* or *Database
  only*, and flagged **looks empty** if the database archive is too small to
  contain anything.

Restoring a backup, and changing what gets captured, are host actions performed
at a terminal. The page shows the exact commands. There is no button for either:
the application has no privileged access to the host, which is what keeps a
problem in the web app from becoming a problem with the machine.

## Audit And Metrics

### Audit (`/admin/audit/`)

- Filter by action, user, endpoint, method, resource, and time range.
- Useful for traceability and access troubleshooting.

### Metrics (`/admin/metrics`)

- Snapshot of resource usage and slow areas.

## High-Risk Operations

- `Purge Parts Data` removes part/BOM/file data and should be used only with backups and explicit maintenance windows.
