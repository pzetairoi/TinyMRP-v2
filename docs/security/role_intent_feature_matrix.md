# Standard role intent and feature wiring

Route guards and `app.services.authorization` are authoritative. Standard roles
are additive: combinations receive the union of their permissions and scopes.
The old exact `admin` slug remains a temporary compatibility bypass, but it is
not a recommended standard role. No role is assigned automatically.

## Role guide

### Administrator

- **See:** All application, security, system, financial, audit, released and unreleased data.
- **Change:** All business and administrative data, imports, exports, shares, archive actions, and active destructive operations.
- **Cannot:** It has no intended application restriction.
- **Scope:** Global.
- **Caveats:** Includes part/file purge and sensitive financial authority; assign sparingly. It receives every active canonical permission and does not depend on the legacy `admin` bypass.
- **Combine with:** Nothing is normally required.

### Security Administrator

- **See:** Users, roles and audit records.
- **Change:** Users, roles, assignments and token revocation.
- **Cannot:** Manage routine business data, settings, storage or maintenance.
- **Scope:** Global security administration only.
- **Caveats:** It is deliberately not a full administrator.
- **Combine with:** System Administrator only when the same person also maintains the installation; use a business role for business work.

### System Administrator

- **See:** Configuration and audit records.
- **Change:** Settings, storage, rebuild and maintenance operations.
- **Cannot:** Manage users/roles or routine business data.
- **Scope:** Global system administration only.
- **Caveats:** Rebuilds and maintenance can affect the whole installation.
- **Combine with:** Security Administrator only when responsibilities overlap; use a business role for business work.

### Engineering/Data Steward

- **See:** Released and unreleased parts, BOMs, normal managed files, comments and markups.
- **Change:** Engineering master data, BOMs, normal files, numbering and shares; run engineering exports.
- **Cannot:** Permanently purge, approve commercial orders, or override approved imports.
- **Scope:** Global engineering data.
- **Caveats:** File replace is not file purge.
- **Combine with:** Quality Reviewer for moderation/review authority, or Import Manager only when approved-data override is genuinely required.

### Import Operator

- **See:** Released and unreleased parts, BOMs and files needed to preview imports.
- **Change:** Run low-risk imports.
- **Cannot:** Overwrite approved/released records or use approved-data override.
- **Scope:** Global import input with no wider engineering mutation grant.
- **Caveats:** Import validation remains authoritative.
- **Combine with:** Engineering/Data Steward when the operator also owns master data.

### Import Manager

- **See:** Released/unreleased parts, BOMs, files and import audit records.
- **Change:** Run ordinary imports and authorised approved-data override imports.
- **Cannot:** Administer users, settings or unrelated business records.
- **Scope:** Global import workflow.
- **Caveats:** This is not a two-person approval workflow. Overrides can modify released data and must be assigned carefully.
- **Combine with:** Engineering/Data Steward only when the same person also maintains engineering data.

### Planner

- **See:** Parts, BOMs, files, comments, drawing markups, jobs, non-financial orders, customers and suppliers for planning context.
- **Change:** Jobs, job BOM/assignments, comments/markups and non-financial order preparation; submit orders, allocate numbers and run job packs.
- **Cannot:** Approve orders or edit financial fields.
- **Scope:** Global planning records.
- **Caveats:** Customer/supplier reads do not grant company financial administration.
- **Combine with:** Procurement or Sales/Customer Service only when that commercial responsibility is also intended.

### Procurement

- **See:** Purchase orders, suppliers, purchasing-related jobs, comments and drawing markups.
- **Change:** Supplier records/financials, comments/markups and the purchase-order workflow, including approval.
- **Cannot:** Exercise sales-order authority or customer financial administration.
- **Scope:** Purchase-side records.
- **Caveats:** The current workflow does not stop the same Procurement user creating and approving an order.
- **Combine with:** Planner when the buyer also plans jobs.

### Sales/Customer Service

- **See:** Sales orders, customers, customer-related jobs, comments and drawing markups.
- **Change:** Customer records/financials, comments/markups and the sales-order workflow, including approval.
- **Cannot:** Exercise purchase-order authority or supplier financial administration.
- **Scope:** Sales-side records.
- **Caveats:** The current workflow does not stop the same Sales user creating and approving an order.
- **Combine with:** Planner when the same person also plans jobs.

### Production Operator

- **See:** Assigned/participant jobs, exact related part revisions, permitted drawing images, comments and markups.
- **Change:** Assigned job stages, material issue, operational comments and drawing markups.
- **Cannot:** Access global orders or companies, edit engineering/BOM master data, or perform commercial actions.
- **Scope:** Assigned jobs only.
- **Caveats:** Adding a user as a participant changes their job and exact-part scope.
- **Combine with:** Normally no other role; Planner broadens job scope globally.

### Quality Reviewer

- **See:** Released/unreleased engineering data, review comments, markups and audit data.
- **Change:** Review comments/markups, moderation and existing review operations.
- **Cannot:** Modify design/BOM data or perform a part-release workflow.
- **Scope:** Global engineering review data.
- **Caveats:** `reviews.approve` applies only to existing review operations, not part release.
- **Combine with:** Engineering/Data Steward only when the reviewer also owns design data.

### Internal Viewer

- **See:** Released parts and non-financial jobs, orders, customers and suppliers.
- **Change:** Nothing.
- **Cannot:** See unreleased parts or financial values; export or mutate data.
- **Scope:** Global internal read-only data.
- **Caveats:** It intentionally excludes annotations and sensitive engineering details.
- **Combine with:** A specialised role only when additional work is required.

### Customer Portal

- **See:** Linked customer organisations, their jobs/sales orders, and exact related part revisions.
- **Change:** Nothing.
- **Cannot:** See suppliers, internal cost, markups, internal comments or unrelated records.
- **Scope:** Linked customers only.
- **Caveats:** Parts must be released/approved unless a custom role also grants `parts.read_unreleased`.
- **Combine with:** Avoid internal roles; combinations can deliberately broaden scope.

### Supplier Portal

- **See:** Linked supplier organisations, issued purchase orders, jobs through `Job.vendors` or those orders, and exact related part revisions.
- **Change:** Nothing.
- **Cannot:** See customer sales pricing, other suppliers, margins or internal comments.
- **Scope:** Linked suppliers and issued purchase relationships only.
- **Caveats:** Parts must be released/approved unless explicitly extended.
- **Combine with:** Avoid internal roles; combinations can deliberately broaden scope.

### Auditor

- **See:** Broad read-only audit, configuration, financial, business and unreleased engineering data.
- **Change:** Nothing.
- **Cannot:** Export, mutate, approve, assign roles or purge.
- **Scope:** Global read-only.
- **Caveats:** Read access includes sensitive financial and unreleased information.
- **Combine with:** Usually nothing; add a role only for a separately intended operational duty.

## Active capability map

| Surface | Read | Mutation or sensitive action | Principal roles |
|---|---|---|---|
| Parts/BOM/files | `parts.read`, `bom.read`, `files.read` | Engineering mutations, file replace, and purge use separate exact permissions | Administrator, Engineering, business readers, portals, Auditor |
| Imports | `imports.preview` | Low-risk, approved execution and approved-data override are separate | Administrator, Import Operator, Import Manager |
| Jobs | `jobs.read` | Job, assignment, BOM, stage, material issue, cancel and archive actions are separate | Administrator, Planner, business roles, Production |
| Orders | `orders.read` | Financial, submit, approve, fulfil, ship, cancel and archive actions are separate | Administrator, Planner, Procurement, Sales |
| Companies | Customer/supplier reads are separate | Update, financial, portal-link and archive actions are separate | Administrator, Planner, Procurement, Sales |
| Comments/markups | `comments.read`, `markups.read` | Writing and moderation are separate | Administrator, Engineering, Planner, Procurement, Sales, Production, Quality; Auditor reads only |
| Security/system | Security and system reads are separate | User/role and configuration/maintenance actions are separate | Administrator and the specialised administrators |

The canonical registry contains only capabilities consumed by current routes or
services. Legacy permission identifiers remain separately registered for stored
role compatibility; they are not recommended canonical permissions.

Custom roles can be deleted by a role administrator only when no users are
assigned. Assigned roles return a conflict and link the administrator to the
affected users; standard catalogue roles and the legacy `admin` role cannot be
deleted through the role editor. This prevents dangling role references.
