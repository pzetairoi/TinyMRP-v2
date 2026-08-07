# Using the Web App

This is the reference for every screen you use day to day. Each section says
what the screen is *for*, then covers the controls, then the things that
commonly catch people out.

## Finding your way around

The top navigation only shows what your role permits, so two people can see
different menus on the same server. The usual entries are:

| Menu | What lives there |
| --- | --- |
| **Parts** | Inventory — the searchable list of every part revision |
| **Jobs** | Manufacturing jobs, their BOMs and stages |
| **Orders** | Purchase and sales orders |
| **Companies** | Customers and suppliers |
| **Import** | Upload packs from SolidWorks |
| **Tools** | Excel compile, add-in and template downloads |
| **Admin** | Users, roles, settings, fields, metrics, audit log |
| Your name (top right) | My Account, Tokens, Help, Logout |

A bell icon appears beside your name when you have notifications.

---

## Inventory

**What it is for:** finding a part revision and getting to its details.

Every row is one part *and revision*. The thumbnail, description and file
badges tell you at a glance what exists.

![The Inventory list: search box, review filter, per-column filters and the Columns picker.](/static/help/img/inventory.png)

### Searching and filtering

- The **search box** covers part number, description, notes and comments in one
  go. It is the fastest way in.
- **Every column has its own filter** in the row beneath the headers. Text
  columns support contains, equals, starts with and their negations, plus
  *is empty* / *is not empty*.
- The **review filter** narrows to parts with pending comments or markups, by
  priority.
- Filters combine. If a search returns less than you expect, clear the column
  filters before assuming data is missing.

### Choosing and ordering columns

Open **Columns** from any column header to get the field picker. There you can:

- Tick or untick the columns you want.
- Reorder them with the **left/right arrows** beside each selected field.
- **Select all**, or **Reset** to the site default.

Your choice is saved to your account, so it follows you to another browser or
machine. You can also drag a column header to reorder it, and drag its edge to
resize.

> **Note:** the Part Number column cannot be removed — it is what identifies
> the row.

### Pick mode

When you add parts to a job BOM or an order line, Inventory opens in **pick
mode**. Tick the parts you want, set a quantity for each, then press **Add
Selected**. The window closes and hands the rows back to the job or order you
came from.

---

## Part Details

**What it is for:** everything about one part revision.

The left panel shows the hero image, quick download buttons for whatever files
exist, who uploaded it, the approval badge, and a **Missing properties**
warning when important fields are empty.

### The approval badge

A tick means the stored approval flag is set; the crossed mark means draft.
This is the same value the Approved filter and the permission rules use, so the
badge and the rest of the app cannot disagree.

If a part you believe is approved shows as draft, the approval property did not
survive the import. Open **Attributes & Notes** and look at what the source
property actually contained — `pending`, `n/a`, `no` or a blank all count as
draft.

### The tabs

| Tab | What it gives you |
| --- | --- |
| **Drawing** | The drawing PDF, in-page |
| **Datasheet** | A linked supplier datasheet, when one exists |
| **Attributes & Notes** | Every property on the part, plus free-text notes |
| **3D Preview** | Rotate the model in the browser (STEP, 3MF, PLY, STL) |
| **Files** | All deliverables and associated files; upload more here |
| **Doc Packs** | Build a download bundle — see below |
| **Other versions** | Jump to another revision of the same part number |
| **Jobs & Orders** | Where this part is used and what has been ordered |
| **Comments & Markups** | Discussion, and red-pen markups on the drawing |
| **Actions** | Refresh file links, share, delete (permission-gated) |

A small badge on **Attributes & Notes** and **Comments & Markups** tells you
there is something to look at.

### Comments and markups

Comments are threaded discussion. Markups are annotations drawn directly on the
drawing. Both can be flagged for review with a priority, which is what the
review filter in Inventory picks up.

You need **comments.read** / **markups.read** to see them, and the matching
`.write` permission to add them.

### The Actions tab

- **Update files** rescans storage for this part and revision and relinks what
  it finds. Use it when files were added on disk outside an import. You can
  include child parts.
- **Share** creates a link for someone without an account (below).
- **Delete part** removes this revision, optionally with children that are not
  used elsewhere.

### Sharing a part outside the system

**Actions → Share** creates a link an outsider can open. You control whether
**child parts**, **Doc Packs**, **attributes** and **unreleased revisions** are
included, and set an **expiry date**. Links can be revoked at any time from the
same tab.

> **Caution:** a share link is a URL containing a secret token. Anyone holding
> it has the access you granted, so set an expiry and revoke links you no
> longer need.

---

## Doc Packs

**What it is for:** producing one download containing exactly the documents
someone else needs — a supplier package, a job folder, a quotation set.

### Choosing the scope

- **Depth** — *top level only* or the *full BOM*.
- **Consumed components** — show or hide parts consumed inside sub-assemblies.
  Shown by default.
- **Classified** — hide, show, or show *only* classified parts.
- **Process** — everything, or only the processes you tick.
- **File types** — which deliverable types to include.

### Choosing the outputs

Any combination of: **selected files**, **Excel BOM** (with the fields you
choose), **PDF binder**, **index PDF**, **visual summary**, **hardware
summary**, **cover page**, **where-used report**, **markup files** and a
**markup report**. A **Fabrication Pack** preset ticks the usual fabrication
set in one click.

### Binder options

With the PDF binder selected you can add a cover page, index, visual list,
where-used report, datasheets, hardware summary, page numbers and flat
patterns — and apply **stamps**: *For quotation*, *Confidential*, *Approved*,
*In progress / Not approved*.

### While it builds

A progress bar shows what is being prepared. Large full-BOM binders take time;
press **Cancel** to stop waiting and get the page back.

> **Note:** Doc Packs need **exports.run**, plus **bom.read** and
> **files.read**. If the controls are disabled, the page names the missing
> permission.

---

## BOM view

Opens the assembly tree for a part, expanding branches on demand so large
assemblies stay responsive. Every node links to its own Part Details.

Below the tree, the **where-used** table answers the opposite question: which
assemblies consume *this* part.

---

## Dashboard

A read-only summary of the database: total parts, recent updates, approved
counts, document coverage (how many parts have a PDF, PNG, DXF, STEP or
datasheet), data-health gaps such as missing material or process, the most
common processes, and recently updated parts.

Use it to spot systematic gaps before they reach a supplier.

---

## Import

**What it is for:** bringing a SolidWorks upload pack into the database.

### The safe sequence

1. Choose the ZIP.
2. Pick a **policy** (below).
3. Press **Preview** — nothing is written.
4. Read the redline.
5. Press **Apply** if it is what you expected.

![The Import page: the four numbered steps, with the policy chooser and its plain-language summary.](/static/help/img/import.png)

The preview shows the top-level part with its image so you can confirm you
picked the right pack. Until that part exists in the database the image comes
from the pack itself and is not stored anywhere.

### The three policies

Properties, BOM and Files are **independent**. Each can be set to:

| Policy | Effect |
| --- | --- |
| **Skip** | Touch nothing in this category |
| **Fill only** | Fill blanks, empty BOMs and missing files |
| **Update drafts** | Also replace existing *draft* data |
| **Override approved (Admin)** | Also change existing *approved* parts |

The presets at the top set all three at once; changing one on its own switches
you to *Custom*.

> **The approval rule in one sentence:** any uploader may import a part that
> arrives already approved, but changing an approved part that already exists
> here — its properties, BOM *or* files — always needs the override permission.

### Reading the redline

Parts are grouped, each with a badge: **New**, **Draft** or **Approved**.
Inside, every property, BOM row and file is listed with what would happen —
*add*, *replace*, *skipped*, *blocked*. Use the tabs to narrow to **Changed**,
**Blocked** or **Modified approved**, and the *changed only* toggle to hide
noise. A **JSON report** download captures the whole plan for a colleague.

**Blocked** means the policy or your permissions stop that one change. The
import can still proceed; blocked items are left alone.

### Files that do not belong to a part

Only parts listed in the BOM files are created. A deliverable whose name does
not match one of them — CAD temp artefacts are the usual culprit — is **skipped
and reported in the warnings**, never turned into a part of its own.

Warnings like *"Skipped … no BOM entry for …"* are this rule working. Check the
file name if you expected that part to exist.

### Duplicate part numbers

If the same part number and revision appears twice in one pack, the import
stops and asks which entry to keep rather than guessing.

### Expected ZIP structure

```text
bom/
  *_FLATBOM.txt
  *_TREEBOM.txt
deliverables/
  <group>/...          png, pdf, dxf, step, edr, 3mf, ply, stl, datasheet
extra/
  <PN>/<REV>/...       associated files
```

### Limits

| Limit | Value |
| --- | --- |
| Maximum ZIP size | 1024 MB |
| Maximum single file | 1024 MB |
| Maximum files per pack | 5000 |

---

## Jobs and Orders

**Jobs** track what you are making: a part, a quantity, a BOM, and stages the
workshop moves through. **Orders** track purchases and sales against them.

From a job you can add parts to its BOM through Inventory pick mode, issue
material and move stages. From an order you add lines the same way. Jobs also
show *parts not yet ordered* and *over-ordered parts*, which is how purchasing
works progressively through a multi-level BOM.

Financial values — prices, margins, credit limits — are a separate permission
from seeing the order itself, so commercial staff and the workshop can share a
screen safely.

> **Caution:** deleting a job warns you first if orders are linked to it, or if
> a customer or supplier would lose access to parts as a result.

---

## Tokens

**My Account → Tokens** creates personal API tokens for the SolidWorks add-in.

The token value is shown **once**, at creation. Copy it then; if you lose it,
revoke it and create another. Revoke any token belonging to a machine you no
longer use.

---

## Tools

Downloads for the SolidWorks toolchain, plus **Excel Compile**, which turns a
spreadsheet of part data into a compiled ZIP.

The download list is generated from what is actually installed on the server,
so it never goes stale. Files are grouped by what you would go looking for:

- **Add-in installer** — the Windows installer for the SolidWorks add-in, newest
  first, plus a direct "Download latest" link.
- **SolidWorks setup** — install these once per workstation so SolidWorks writes
  the custom properties TinyMRP reads back. The two `.prtprp` / `.asmprp` files
  are the custom property tabs for parts and assemblies; `TinyMRP.swp` is the
  macro.
- **BOM table templates** — SolidWorks BOM table formats whose columns match
  what the importer expects. Using one of these avoids having to remap columns
  on every import.
- **Excel helpers** — workbooks for editing properties in bulk and the template
  for the document compiler.

---

## Admin

Available to administrators, and in part to security administrators.

| Page | Use it to |
| --- | --- |
| **Users** | Create accounts, assign roles, reset access |
| **Roles & permissions** | Build roles from the permission catalogue |
| **Application settings** | Branding, limits, storage |
| **Fields & exports** | Rename fields, add custom ones, set approval rules |
| **SolidWorks add-in** | Publish the build users download; manage numbering schemes |
| **System metrics** | Environment, storage and record counts for diagnosis |
| **Audit log** | Who did what, when |
| **Rescan files** | Relink storage to parts across the whole database |
| **Purge parts data** | Delete data deliberately — see below |

### Rebuilding after a settings change

If you change field mappings or approval rules, existing parts keep their old
computed values until you rebuild. **Fields & exports** has a rebuild action
that recomputes them for every part. It is safe to run repeatedly.

### Rescanning files

**Rescan files** walks the storage tree and relinks deliverables to parts. Use
it after moving storage, restoring a backup, or copying files in outside an
import. It runs in the background with a progress bar and can be cancelled.

> **Caution:** *Purge parts data* permanently deletes what you select — BOMs,
> files, properties, comments, markups, whole parts, and even users and custom
> roles. It requires you to type a confirmation phrase. There is no undo. Take
> a database backup before a large purge.
