# Getting Started

TinyMRP keeps one trusted copy of your engineering data. Parts, BOMs and CAD
deliverables come out of SolidWorks, land here through an import, and everyone
else — workshop, purchasing, customers, suppliers — sees exactly the slice they
are allowed to see.

If you read nothing else, read this page.

## The five-minute version

1. **Engineering exports an upload pack** from SolidWorks: a ZIP containing a
   BOM and the deliverables (PDF, STEP, PNG, DXF, and so on).
2. **Someone imports it** on the Import page. You always *preview* first: the
   app shows a line-by-line redline of what would change before anything is
   written.
3. **Parts appear in Inventory.** Each row is one part *and revision*.
4. **Part Details** is where the work happens: drawings, 3D previews, files,
   comments, markups and Doc Packs.
5. **Doc Packs** bundle what you need — a PDF binder, an Excel BOM, selected
   files — into one download for a supplier, a job folder or a quote.

## The one idea that explains everything

**A part is identified by its part number *and* its revision.**

`3950-35` rev `A` and `3950-35` rev `B` are two separate records, each with its
own files, BOM and approval state. Almost every confusing moment in this app
comes from looking at a different revision than you expected. The revision is
shown next to the part number everywhere; when it is blank, the part simply has
no revision set, which is normal in many workflows.

## Approved vs draft

Every part revision is either **approved** or **draft** (unapproved). The
approval flag is worked out *once*, when the part is imported or saved, from
whatever your CAD properties happen to call it — `approved`, `approvedby`,
`released`, and so on. From then on a single stored value drives everything:
the badge on Part Details, the Approved filter in Inventory, what customers and
suppliers can see, and what an import is allowed to overwrite.

Two consequences worth knowing:

- If a valid approver name is present, the part counts as **approved**.
- Values like `pending`, `n/a`, `TBC`, `no` or a blank field mean **not
  approved**.

> **Why this matters:** anyone with upload rights can import a part that
> arrives *already* approved. But once an approved part exists here, changing
> it requires the override permission. See **Roles and permissions**.

## What you can see depends on your role

Menus, buttons and even individual table rows adapt to your permissions. If a
menu entry is missing, your role does not include it — that is the app working
correctly, not a fault. Two rules answer most questions:

- Without **parts.read_unreleased**, you only see approved parts.
- Customers and suppliers only see parts reachable from *their own* jobs and
  orders.

## Where to go next

| I want to… | Go to |
| --- | --- |
| Find a part | **Inventory** |
| Look at drawings, files, 3D, comments | **Part Details** |
| Get data in from SolidWorks | **Import** |
| Produce a PDF binder or Excel BOM | Part Details → **Doc Packs** |
| Understand why I cannot do something | **Roles and permissions** |
| Fix something that went wrong | **Troubleshooting** |

## A note on this help

Every screen, option and limit described here was checked against the running
application. Where the app enforces a rule that is easy to trip over, it is
called out in a box like the one above rather than buried in prose.
