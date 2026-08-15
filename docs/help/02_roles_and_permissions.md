# Roles and Permissions

Most "why can't I…" questions are answered here. TinyMRP hides what you cannot
use rather than showing you a dead button, so a missing menu is usually the
answer rather than a fault.

## How access is decided

Three things combine:

1. **Your role's permissions** — what actions you may take at all.
2. **Scope** — which records you can see. Customers and suppliers only reach
   parts connected to their own jobs and orders.
3. **The part's approval state** — approved parts are protected from change.

A permission never implies another. Holding `parts.read` does not grant
`parts.update`; each capability is granted explicitly.

## The standard roles

| Role | In plain terms |
| --- | --- |
| **Administrator** | Everything, including approved-data override and purge. |
| **Security Administrator** | Users, roles, tokens and audit only. No parts, no jobs. |
| **Engineering Manager** | All engineering data, plus review approval, moderation and the approved-data override. No purge, no commercial. |
| **Engineering** | Parts, BOMs, files, shares, exports, part numbers, and imports including overwriting drafts. Cannot touch approved data. |
| **Commercial** | The full order workflow, customers and suppliers with financials, job planning. No engineering changes. |
| **Internal** | Reads released business data, comments, pulls documentation. No financials, no drafts, no changes. |
| **Workshop** | Job stages and material issue, released part documents, comments and markups. |
| **Customer** | Read-only view of *their* jobs, sales orders and released revisions. |
| **Supplier** | Read-only view of *their* purchase orders, related jobs and released revisions. |
| **Auditor** | Broad read-only, including financials and drafts. No exports, no changes. |

Roles are editable and you can create your own; these are the shipped defaults.

## The rules that surprise people

### You only see approved parts by default

Seeing a **draft** part needs `parts.read_unreleased`. Without it, Inventory,
search and BOM views quietly skip unapproved revisions. This is why a colleague
may see a part you cannot.

The same Inventory screen, opened by a customer account, shows only the approved
parts reachable from that customer's own jobs and sales orders — and the Import, Tools and
Admin menus are gone entirely:

![Inventory as a customer: only the released contractual subtree, and no Import, Tools or Admin menu.](/static/help/img/customer-portal.png)

Suppliers are narrower again: a vendor association may expose job context, but
engineering data comes only from that supplier's purchase-order lines and their
children. A sales-order supplier field never grants access.

Unapproved nodes stop traversal by default. If a named external reviewer really
must inspect held data, assign `parts.read_unreleased` in addition to the
customer or supplier role. This removes only the approval barrier; it does not
broaden the linked company, jobs, order kind or supplier PO-line subtree.

![A customer reviews the released parent drawing and requests approval for CV03-F02 REV B because the held child is correctly unavailable.](/static/help/img/customer-approval-request.png)

### Approval comes from CAD, not from TinyMRP

There is no button here that approves a part. Approval is read out of the
columns of an imported pack, which is how it arrives from SolidWorks and PDM.

Anyone with upload rights may therefore import a part that arrives already
approved — that is normal engineering output, not a privileged act. Publishing
a release onto a draft is allowed for the same reason: it destroys nothing.

Once a part is approved here, changing **anything** on it — properties, BOM,
files, or the approval itself — requires `imports.override_approved`, which by
default only Administrators and Engineering Managers hold. Everything else about
an import, including overwriting a draft outright, sits with Engineering.

### Approval status is visible to everyone who can see the part

Whether a part is approved is part of the part. Who approved it and when are
restricted to reviewers and auditors.

### Financial values are separate

`orders.read` shows an order. `orders.financial.read` shows its prices. The
same split applies to customers and suppliers, so the workshop can see what to
build without seeing what it cost.

### Comments and markups are separately gated

Reading, writing and moderating are three different permissions. Moderation —
resolving or removing someone else's contribution — sits with managers.

## When something is refused

The app tells you which permission is missing. Take that name to whoever
administers roles; it maps directly to a tick box on the role editor.

On the Import page, missing permissions appear in the redline *before* you
apply, so you can see the problem without risking a partial import.

## For administrators

### Building a role

**Admin → Roles & permissions** lists every permission grouped by area. Each
one gates a real screen or action — there are no decorative entries.

![The role editor, showing the standard roles with their permission counts and drift status.](/static/help/img/roles.png)

Start from a standard role, copy it, and remove what the job does not need. It
is easier to defend a role that grew from a template than one assembled from
scratch.

### Testing a role without logging out

If the permission-test environment is enabled on your server, an administrator
can **impersonate** a test user from the account menu, below Logout. You see
exactly what that role sees, then return with one click. Actions taken while
impersonating are recorded in the audit log against both identities.

Impersonation is limited to purpose-made test accounts and never applies to
real users or other administrators.

The seeded environment uses the owner-approved `CV03-TR-A01` revision A sample
and its BOM children. It includes complete-unit and spare-parts customers,
four process suppliers, linked jobs and orders, released Part/File records,
general-comment conversations, and open/resolved drawing-markup reviews. The
extra customer/supplier accounts let an administrator follow a review from
each participant's restricted view instead of simulating every reply as one
user.

The corresponding managed-file fixture lives in
`sample_data/cv03_tr_a01_rev_a`. For an isolated development installation,
copy it into the selected deliverables root with:

```text
python tools/install_sample_dataset.py --destination <deliverables-root>
```

Existing files are skipped. Add `--overwrite` only when you intentionally want
the checksum-pinned sample copy to replace a same-named file.
