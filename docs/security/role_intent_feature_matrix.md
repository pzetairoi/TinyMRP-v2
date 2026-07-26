# Role intent and feature-wiring matrix

This matrix records the application surface at the role-wiring audit. Route
guards and `app.services.authorization` remain authoritative; this document is
an inventory, not a second policy engine.

| Feature | View | Create / update | Transition / financial / destructive | Scope and entry points | Intended standard roles |
|---|---|---|---|---|---|
| Parts and revision history | `parts.read`; unreleased requires `parts.read_unreleased` | `parts.create`, `parts.update`, `parts.revise` | Purge requires `parts.purge` and, for file deletion, `files.purge` | Parts navbar and `/ui/parts`; global released scope, exact relationship revisions for portal/production roles | Engineering, Import roles, Planner, Procurement, Sales, Production, Quality, Viewer, portals, Auditor |
| BOM views | `bom.read` plus authorised root part | `bom.update`; job BOM uses `jobs.bom.update` | — | `/ui/bom/<pn>` and BOM APIs use exact part scope | Engineering, Import roles, Planner, Procurement, Sales, Production, Quality, Viewer, portals, Auditor |
| Managed and associated files | `files.read` | `files.add`, `files.replace` | Purge: `files.purge` | Exact part scope plus file-category policy; no standalone navbar item | Engineering maintains; other engineering/business readers consume permitted files |
| Comments and markups | `comments.read`, `markups.read` | `comments.write`, `markups.write` | `comments.moderate`, `markups.moderate` | Part detail; portal field policy removes internal content | Engineering and Quality; Production operational comments; Auditor reads |
| Jobs | `jobs.read` | `jobs.create`, `jobs.update`, `jobs.assign`, `jobs.bom.update` | Stage/material operations use their exact permissions; archive uses `jobs.archive` | Jobs navbar; portal, assigned, purchasing, customer-business, or global contributor scope | Planner, Procurement, Sales, Production, Viewer, portals, Auditor |
| Orders | `orders.read` | `orders.create`, `orders.update` | Submit/approve/fulfil/ship/cancel/archive use exact permissions; monetary fields use `orders.financial.*` | Orders navbar; Procurement purchase-only, Sales sales-only, portals linked-kind-only | Planner, Procurement, Sales, Viewer, portals, Auditor |
| Customers | `customers.read` | `customers.update` | Financial fields use `customers.financial.*`; links use `customers.portal_users.manage`; archive uses `customers.archive` | Companies menu; customer portal linked organisations only | Planner, Sales, Viewer, Customer Portal, Auditor |
| Suppliers | `suppliers.read` | `suppliers.update` | Financial fields use `suppliers.financial.*`; links use `suppliers.portal_users.manage`; archive uses `suppliers.archive` | Companies menu; supplier portal linked organisations only | Planner, Procurement, Viewer, Supplier Portal, Auditor |
| Numbering | Relevant read plus `numbering.allocate` | `numbering.allocate`; administration uses `numbering.manage` | — | Part creation/revision and add-in administration | Engineering, Planner; system/legacy administrators for configuration |
| Imports | `imports.preview` | `imports.execute_low_risk` or `imports.execute_approved` | Approved override requires both `imports.execute_approved` and `imports.override_approved` | Import navbar and `/ui/upload-pack`; no unsupported approval screens | Import Operator, Import Approver |
| Tools | `exports.run` or legacy `tools.view` | — | Individual routes enforce their real capability | Tools navbar and `/tools/`; cards are capability-filtered | Engineering, Planner, Procurement, Sales; legacy static-tool users |
| Excel Compile | `exports.run` plus export preflight reads | `exports.run` | — | Tools card and `/tools/excelcompile` | Engineering, Planner, Procurement, Sales |
| Part document packs | `exports.run`, `parts.read`, `bom.read`, `files.read` | `exports.run` | Markup options additionally require `markups.read` | Part detail/API; exact part/BOM/file scope | Engineering; other exporting roles only for authorised parts |
| Job document packs | Job-pack route also requires `jobs.read` | `exports.run` | Same underlying part/BOM/file and markup checks | Job detail | Planner, Procurement, Sales |
| Order document packs | Order-pack route also requires `orders.read` | `exports.run` | Same underlying part/BOM/file and markup checks | Order detail; order-kind scope remains enforced | Procurement purchase orders; Sales sales orders |
| Fabrication packs | Same as the containing document-pack route | `exports.run` | — | A real document-pack preset, not a separate authority | Export-capable engineering/business roles |
| Public shares | Share delivery is token scoped | `shares.create`, `shares.revoke` | — | Part detail and public share endpoints; exact part and release policy | Engineering |
| Users | `security.users.read` | `security.users.manage` | Role assignment also requires `security.assignments.manage`; token revocation uses `security.tokens.revoke` | Filtered Admin launcher/overview | Security Administrator; Auditor read-only |
| Roles | `security.roles.read` | `security.roles.manage` | Standard-role restore is explicit and does not change assignments | Filtered Admin launcher/overview | Security Administrator; Auditor read-only |
| Audit | `audit.read` | — | Test event requires `system.maintenance` | Admin launcher and `/admin/audit/` | Security/System Administrators, Import Approver, Quality, Auditor |
| Application settings | `system.config.read` | `system.config.manage` | Recompute requires `system.rebuild` | Filtered Admin launcher/overview | System Administrator; Auditor read-only |
| Fields and exports configuration | `system.config.read` | `system.config.manage` | Rebuild uses `system.rebuild` | Admin configuration shell, shown to configuration managers | System Administrator |
| SolidWorks add-in administration | Configuration/storage authority | `system.config.manage`, `system.storage.manage`, or `numbering.manage` | — | Filtered Admin configuration shell | System Administrator and explicitly authorised legacy numbering administrators |
| System metrics | `system.maintenance` | — | Maintenance test operations use `system.maintenance` | Filtered Admin system section | System Administrator |
| Purge and destructive administration | — | — | Parts purge requires both `parts.purge` and `files.purge` | Filtered danger-zone link and protected route | No standard role |

## Standard-role navigation result

| Role | Canonical navigation |
|---|---|
| Security Administrator | Admin: Users, Roles & permissions, enabled test setup, Audit |
| System Administrator | Admin: Settings, Fields & exports, SolidWorks add-in, Metrics, Audit |
| Engineering/Data Steward | Parts, Tools |
| Import Operator | Parts, Import |
| Import Approver | Parts, Import, Audit |
| Planner | Parts, Jobs, Orders, Customers, Suppliers, Tools |
| Procurement | Parts, purchasing-relevant Jobs, purchase Orders, Suppliers, Tools |
| Sales/Customer Service | Parts, customer Jobs, sales Orders, Customers, Tools |
| Production Operator | Parts, assigned Jobs |
| Quality Reviewer | Parts, Audit |
| Internal Viewer | Parts, Jobs, Orders, Customers, Suppliers |
| Customer Portal | Parts, linked Jobs, linked sales Orders, My Customer |
| Supplier Portal | Parts, vendor/PO-linked Jobs, issued purchase Orders, My Supplier |
| Auditor | read-only Admin, Parts, Jobs, Orders, Customers, Suppliers, Audit |
| Break-glass Administrator | No authority-driven navigation |

## Canonical permission coverage

`ACTIVE` means a current route, service boundary, field policy, or meaningful
visible control consumes the permission. `RESERVED` means the stable identifier
is intentionally retained but no corresponding operation is presented.
Reserved identifiers remain in the registry but are not assigned to standard
roles.

### ACTIVE

`audit.read`; all `security.*`; all `system.*`; `parts.read`,
`parts.read_unreleased`, `parts.create`, `parts.update`, `parts.revise`,
`parts.purge`; `bom.read`, `bom.update`; `files.read`, `files.add`,
`files.replace`, `files.purge`; `numbering.allocate`, `numbering.manage`,
`exports.run`, `shares.create`, `shares.revoke`; `imports.preview`,
`imports.execute_low_risk`, `imports.execute_approved`,
`imports.override_approved`; all `comments.*`, all `markups.*`,
`reviews.approve`; all `jobs.*` except `jobs.material.receive`; all
`orders.*`; all `customers.*`; all `suppliers.*`.

### RESERVED

- `parts.release.approve`: retained for a future release operation; no release
  action is presented.
- `parts.archive`, `parts.restore`: lifecycle identifiers retained without a
  current part archive/restore route.
- `files.archive`, `files.restore`: lifecycle identifiers retained without a
  current managed-file archive/restore route.
- `imports.review_high_risk`, `imports.approve_high_risk`,
  `imports.rollback`: retained for compatibility/future workflow; no screens or
  controls claim these workflows exist.
- `jobs.material.receive`: retained for the intended material-receipt lifecycle;
  the current product only exposes material reservation/issue.

### UNUSED

None. Every canonical identifier is either consumed today or has an explicit
compatibility/lifecycle reason above. Legacy identifiers remain separately
registered for compatibility and are not used for canonical presentation,
except `tools.view` for the intentionally legacy static installer/download
surface.
