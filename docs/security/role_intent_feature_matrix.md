# Standard role intent and feature wiring

Route guards and `app.services.authorization` are authoritative. Standard roles
are additive: combinations receive the union of their permissions and scopes.
The old exact `admin` slug remains a temporary compatibility bypass, but it is
not a recommended standard role. No role is assigned automatically.

Ten roles cover the intended organisation. Superseded slugs
(`system_administrator`, `engineering_data_steward`, `import_operator`,
`import_approver`, `planner`, `procurement`, `sales_customer_service`,
`production_operator`, `internal_viewer`, `customer_portal`,
`supplier_portal`) are no longer catalogue roles. Existing role documents and
their user assignments survive as custom roles and stay correctly scoped,
because `_scope_modes` still recognises the superseded portal and assigned-job
names. Reassign those users, then delete the leftover custom roles.

## Role guide

### Administrator

- **See:** All business, security, system, financial, audit, released and unreleased data.
- **Change:** Everything: users, roles and assignments, all business data, imports including approved override, exports, shares, archive and purge, and system configuration, storage, rebuild and maintenance.
- **Cannot:** It has no intended application restriction.
- **Scope:** Global.
- **Caveats:** Includes user/role administration, purge and sensitive financial authority; assign sparingly and prefer a narrower role for day-to-day work.
- **Combine with:** Nothing is normally required.

### Security Administrator

- **See:** Users, roles and audit records.
- **Change:** Users, roles, assignments and token revocation.
- **Cannot:** Manage business data, settings, storage or maintenance.
- **Scope:** Global security administration only.
- **Caveats:** Use this to delegate account administration to someone who must not hold business authority.
- **Combine with:** A business role for business work.

### Engineering Manager

- **See:** Everything Engineering sees, plus audit records.
- **Change:** Everything Engineering changes, plus approved-data override imports, comment/markup moderation, existing review approvals and numbering scheme administration.
- **Cannot:** Purge parts or files, run the commercial order workflow, or administer users.
- **Scope:** Global engineering data.
- **Caveats:** Approved-data override can modify released records; `reviews.approve` applies only to existing review operations, not part release.
- **Combine with:** Nothing is normally required.

### Engineering

- **See:** Released and unreleased parts, BOMs, managed files, comments, markups, jobs and orders.
- **Change:** Parts, BOMs, managed files, numbering allocation, shares and exports; runs low-risk imports.
- **Cannot:** Overwrite approved data, purge, moderate, or perform commercial actions.
- **Scope:** Global engineering data.
- **Caveats:** File replace is not file purge. Imports that touch approved records require Engineering Manager.
- **Combine with:** Nothing is normally required.

### Commercial (Sales & Procurement)

- **See:** Parts, BOMs, files, comments, markups, all jobs, all orders with financials, and all customers and suppliers with financials.
- **Change:** The full purchase and sales order workflow including approval, customer and supplier records and financials, company archiving, job planning, assignment and job BOMs, numbering allocation and exports.
- **Cannot:** Mutate engineering master data, run imports, administer portal users, or purge.
- **Scope:** Company-wide commercial records.
- **Caveats:** Purchase and sales authority are combined, so the same person can raise and approve either kind of order. Granting portal access to an external user stays an administrator duty.
- **Combine with:** Nothing is normally required.

### Internal (Other Department)

- **See:** Released parts, BOMs and files, plus non-financial jobs, orders, customers and suppliers.
- **Change:** Comments only.
- **Cannot:** See financial values or unreleased engineering data; mutate business records or run imports.
- **Scope:** Global internal read-only data.
- **Caveats:** Exports are permitted so other departments can pull documentation.
- **Combine with:** A specialised role only when additional work is required.

### Workshop

- **See:** All jobs, released part revisions, permitted drawings, comments and markups.
- **Change:** Job stages, material issue, comments and drawing markups.
- **Cannot:** Access orders or companies, edit job or engineering master data, or export.
- **Scope:** Shop-wide jobs.
- **Caveats:** Visibility is deliberately not limited to participant jobs, so no participant bookkeeping is required to keep the shop floor working.
- **Combine with:** Normally no other role.

### Customer

- **See:** Linked customer organisations, their jobs and sales orders, and exact related part revisions.
- **Change:** Nothing.
- **Cannot:** See suppliers, internal cost, markups, internal comments or unrelated records.
- **Scope:** Linked customers only.
- **Caveats:** Parts must be released/approved unless a custom role also grants `parts.read_unreleased`. Combining with an internal role widens scope to that role's.
- **Combine with:** Avoid internal roles.

### Supplier

- **See:** Linked supplier organisations, issued purchase orders, jobs through `Job.vendors` or those orders, and exact related part revisions.
- **Change:** Nothing.
- **Cannot:** See customer sales pricing, other suppliers, margins or internal comments.
- **Scope:** Linked suppliers and issued purchase relationships only.
- **Caveats:** Parts must be released/approved unless explicitly extended.
- **Combine with:** Avoid internal roles.

### Auditor

- **See:** Broad read-only audit, configuration, financial, business and unreleased engineering data.
- **Change:** Nothing.
- **Cannot:** Export, mutate, approve, assign roles or purge.
- **Scope:** Global read-only.
- **Caveats:** Read access includes sensitive financial and unreleased information.
- **Combine with:** Usually nothing.

## Active capability map

| Surface | Read | Mutation or sensitive action | Principal roles |
|---|---|---|---|
| Parts/BOM/files | `parts.read`, `bom.read`, `files.read` | Engineering mutations, file replace, and purge use separate exact permissions | Administrator, Engineering roles, business readers, portals, Auditor |
| Imports | `imports.preview` | Low-risk execution and approved-data override are separate | Administrator, Engineering, Engineering Manager |
| Jobs | `jobs.read` | Job, assignment, BOM, stage, material issue, cancel and archive actions are separate | Administrator, Commercial, Workshop |
| Orders | `orders.read` | Financial, submit, approve, fulfil, ship, cancel and archive actions are separate | Administrator, Commercial |
| Companies | Customer/supplier reads are separate | Update, financial, portal-link and archive actions are separate | Administrator, Commercial |
| Comments/markups | `comments.read`, `markups.read` | Writing and moderation are separate | Administrator, Engineering roles, Commercial, Internal, Workshop; Auditor reads only |
| Security/system | Security and system reads are separate | User/role and configuration/maintenance actions are separate | Administrator, Security Administrator |
| Tools/downloads | `exports.run` gates the Tools page | The SolidWorks add-in installer, macro and Excel compiler downloads use the same `exports.run` gate as the page | Administrator, Engineering roles, Commercial, Internal |

The canonical registry contains only capabilities consumed by current routes or
services. Legacy permission identifiers remain separately registered for stored
role compatibility; they are not recommended canonical permissions.

Custom roles can be deleted by a role administrator only when no users are
assigned. Assigned roles return a conflict and link the administrator to the
affected users; standard catalogue roles and the legacy `admin` role cannot be
deleted through the role editor. This prevents dangling role references.

## Adding a scoped role

`_scope_modes` in `app/services/authorization.py` ends its role dispatch by
adding the `global` mode, so a role name it does not recognise receives
unrestricted visibility rather than failing closed. Any new role whose
visibility must stay narrowed has to be added both to the `fixed` map in
`_scope_modes` and to `scoped_roles` in `_build_scope_context`.
`test_scoped_standard_roles_are_registered_in_the_scope_map` enforces this for
the catalogue.
