# Configuration

This page is for admin users who maintain TinyMRP operations.

## Admin Dashboard (`/admin`)

Main admin modules:

- Users
- Roles
- Audit Log
- Metrics
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

- Customer-linked users see customer-relevant data.
- Supplier-linked users see supplier-relevant data.
- Internal privileged roles remain unscoped.

This scoping is enforced server-side on jobs, orders, customers, suppliers, parts, and related views.

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

## Audit And Metrics

### Audit (`/admin/audit/`)

- Filter by action, user, endpoint, method, resource, and time range.
- Useful for traceability and access troubleshooting.

### Metrics (`/admin/metrics`)

- Snapshot of resource usage and slow areas.

## High-Risk Operations

- `Purge Parts Data` removes part/BOM/file data and should be used only with backups and explicit maintenance windows.
