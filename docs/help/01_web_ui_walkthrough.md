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

## Home and notifications

**Where to find it:** sign in, or choose **My Account** from your name in the
top-right menu.

The **Notifications** panel is a work queue. When you first open Home it shows
only items that are still current:

- An open comment or drawing review appears once, using its latest activity.
- Resolving or deleting the comment/review moves its notifications out of the
  current list.
- **Show history** reveals resolved, deleted and earlier activity without
  mixing it into the work still to do. The button appears when history exists.

To work through the list:

1. Open a notification and deal with the linked comment or review on the part.
2. Resolve it when the work is complete, or delete it when the conversation
   should be removed from the part.
3. Return to Home. The item is now under **Show history**, not in the current
   list. Reopening the conversation makes its latest notification current
   again.

**Mark all read** clears the unread emphasis; it does not close work. An open
comment or review remains in the current list until somebody resolves or
deletes it. History keeps the notification text for context, but a deleted
comment is not restored to the part by opening its historical notification.

### Who can resolve or delete a conversation

**You can always resolve, reopen, delete or reprioritise a comment or review
thread you raised yourself** — whatever your role. Customers, suppliers and
workshop users can clear their own items, so their queue empties like anybody
else's.

Acting on *someone else's* comment or thread is moderation, and needs
**Comment moderation** (`comments.moderate`) or **Markup moderation**
(`markups.moderate`). Those sit in the Engineering Manager role by default.
Without them the attempt is refused and the conversation is left untouched.

Reading alone is never enough: a role with only **Comments read** cannot
resolve or delete anything, including its own.

**Troubleshooting:** if a status changed in another browser tab, refresh Home.
Items for parts or comments you can no longer access are not shown in either
the current list or history.

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

![Part Details with the model preview, drawing, download shortcuts and working tabs visible together.](/static/help/img/part-detail.png)

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

### Comments and drawing markups

**Where to find it:** open a part revision, then choose **Comments & Markups**.
The same workspace keeps general discussion, drawing annotations and their
review threads together.

![A populated review history with customer, supplier, engineering and workshop participants, priorities and resolved/open states.](/static/help/img/review-conversations.png)

General comments and drawing-linked review threads are chronological
conversations. Each card keeps its original author, replies, priority and
open/resolved state, so a supplier answer or workshop verification does not
erase the customer's question. Reply on the existing card when the subject is
the same; create a new comment or review when it needs its own status.

![The expanded drawing-markup workspace: review panel, drawing canvas, annotation tools and save/view controls.](/static/help/img/drawing-markups.png)

To mark up a drawing:

1. Pick **Arrow**, **Rectangle**, **Ellipse**, **Revision cloud**, **Text / callout**
   or **Freehand** from the left tool rail. Choose the colour and line width.
2. Draw on the canvas. Use **Select** to move or resize an annotation, and
   **Pan**, **Zoom in/out** or **Fit view** to move around the sheet.
3. Describe the issue when the review form opens. Set its priority and press
   **Create review**. This saves the new annotation and its linked review.
4. If you skip the review, press **Save** in the right rail before leaving.

**Add comment** creates a general part comment. To attach a later comment to
one or more annotations, select them first; the button changes to **Add review
comment**. Use **open / resolved / all** to filter the discussion. Resolved
annotations are hidden by default and can be revealed with **Resolved**.

**PNG** downloads the drawing with the visible annotations flattened on top;
**Open PDF** opens the original drawing. The browser editor needs a drawing PNG
or preview PNG as its canvas—the PDF alone is not drawn on directly.

You need **comments.read** / **markups.read** to see the respective content,
and **comments.write** / **markups.write** to add it. If the status says
**Conflict – reload required**, another save won the race: reload the markup
layer and repeat your unsaved change instead of overwriting their work.

### The Actions tab

- **Update files** rescans storage for this part and revision and relinks what
  it finds. Use it when files were added on disk outside an import. You can
  include child parts.
- **Share** creates a link for someone without an account, at a chosen access
  level (below).
- **Delete part** removes this revision, optionally with children that are not
  used elsewhere.

### Sharing a part outside the system

**Actions → Share** creates a link an outsider can open with no account. Pick
an **expiry**, choose an **access level**, then create the link. The raw URL is
shown once, at creation time.

**Every share always shows the preview images and the 3D viewer.** That is the
floor and it cannot be switched off — a link that shows nothing would not be
worth sending. Note that rotating the model in the browser means the mesh file
itself reaches the viewer; a mesh carries no dimensions or tolerances, unlike a
STEP model.

Each level adds to that floor:

| Level | Adds |
|---|---|
| **Preview** | nothing — images and the 3D viewer only |
| **Review** | drawings (drawing PNG and PDF), datasheets, part attributes |
| **Full access** | the above plus STEP/DXF/eDrawings, all associated files, and Doc Packs |

**Customise what this level grants** opens the individual switches behind the
levels, so you can build a combination no level covers — a datasheet with no
drawing, or a drawing with no STEP model. Ticking a box that no longer matches
a named level is fine; the link stores the switches, not the level name.

- **Drawings** — the drawing PNG and the drawing PDF. A drawing carries
  dimensions and tolerances, which the shaded preview does not.
- **Neutral CAD** — STEP, DXF and eDrawings downloads. This is the geometry a
  supplier can quote and cut from.
- **Datasheets** — the component datasheet where one is on file. This is the
  manufacturer's own published document, so it is separate from your uploads.
- **All files** — associated uploads (dwg, xlsx, docx and the rest) in the
  **Files** tab. Files whose source or label reads *internal*, *private*,
  *review*, *markup* or *audit* are never shared, at any level.
- **Attributes** — material, finish, mass and the **Attributes** tab.
- **Doc Packs** — lets the recipient build a document pack. A pack can only
  ever contain file types the same link already grants, so a Preview link
  cannot package a STEP file by asking for a fabrication pack.

**Include BOM children** is a separate axis from the level. The level decides
what each part shows; this decides how many parts the link reaches. With it on,
the shared page carries a **BOM** table the recipient can expand and click
through, and every descendant part shows at the same level as the root. With it
off the link reaches exactly one part and one revision, and **the BOM table is
not shown at all** — there is no BOM to show, so no empty heading appears.

### What the recipient actually sees

The shared page only shows sections the link can fill:

| Section | Appears when |
|---|---|
| Preview image, 3D viewer | always |
| **Drawing** tab | Drawings granted, and a drawing exists |
| **Datasheet** tab | Datasheets granted, and one is on file |
| **Attributes** tab | Attributes granted |
| **Files** tab | any download is granted — Drawings, Neutral CAD, Datasheets or All files |
| **Doc Packs** tab | Doc Packs granted |
| **BOM** table | Include BOM children ticked |

At the Preview level there is no **Files** tab: the link grants no downloads, so
the tab would list only the image and the mesh the viewer is already showing.

A shared link carries no account, so the recipient never sees a message about
missing permissions. What the link grants is the whole answer — if a section is
there, they can use it.

**Doc Packs** does not need **Include BOM children**. Without children the pack
covers this part alone, which is usually what a single-part enquiry wants.

Doc Packs at the Preview level cannot contain PNGs. A pack picks files by type,
and a preview image and a drawing export are the same type — so a link that may
not show drawings cannot package images either. Grant **Drawings** if the
recipient needs images in their pack.

Review markups and internal comments are never exposed on a shared link,
whatever the level. Links can be revoked at any time from the same tab, and the
**Grants** column in the list shows what each existing link actually gives.

> **Links created before access levels existed** keep granting what they
> granted when they were sent — drawings, CAD and all files. Re-create the
> link if you want it narrowed.

> **Caution:** a share link is a URL containing a secret token. Anyone holding
> it has the access you granted, so set an expiry and revoke links you no
> longer need.

---

## Doc Packs

**What it is for:** producing one download containing exactly the documents
someone else needs — a supplier package, a job folder, a quotation set.

### Choosing the scope

- **Depth** — *this part + its children*, or the *full BOM (all levels)*.
  *This part + its children* covers the assembly itself and the components
  directly under it, and stops there: a sub-assembly appears as a line item,
  but the parts inside that sub-assembly do not. It applies to everything the
  pack produces — the files, the Excel BOM, the binder, the visual summary and
  the hardware summary all cover exactly those two levels. *Full BOM* walks
  every level down to the last component.
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

![A multi-level BOM with one assembly expanded to show its child rows and quantities.](/static/help/img/bom-tree.png)

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

> The next chapter, [Import: what each choice does](#import-what-each-choice-does),
> is the full reference: exactly what fills, replaces, removes or is blocked,
> how approval behaves, who is allowed to do what, an eleven-step exercise with
> ready-made test packs, and an FAQ.

### The safe sequence

1. Choose the ZIP.
2. Choose how it should be written (below).
3. Press **Preview** — nothing is written.
4. Read the redline.
5. Press **Apply**. It only becomes available once the preview matches what you
   are about to send.

![The Import page: the four numbered steps, with the two choices and their plain-language summary.](/static/help/img/import.png)

The preview shows the top-level part with its image so you can confirm you
picked the right pack. Until that part exists in the database the image comes
from the pack itself and is not stored anywhere.

### The two choices

| Choice | Effect |
| --- | --- |
| **Add without overwriting** | Fills blanks, empty BOMs and missing files, and records a release the pack carries |
| **Overwrite with the pack** | Makes the part match the pack: values are replaced, and properties the pack does not carry are **removed** |
| **+ “also approved”** | Extends the overwrite to approved part/revisions. Needs `imports.override_approved` |

The advanced panel can set Properties, BOM and Files separately, including
*Skip*.

> **Overwrite only with a complete export.** A partial pack — a few columns put
> together by hand — will remove everything it omits. The preview shows those as
> *clear* rows before anything happens.

> **The approval rule in one sentence:** approval always comes from the pack,
> never from TinyMRP; a release is applied without overwriting, but changing or
> removing the approval of a part that is already approved needs the tick.

### Reading the redline

A banner says whether this is a **PREVIEW** or an applied **IMPORTED** run, and
after an apply it carries the counts. Parts are grouped by what happens to them
— **Blocked**, **Approved parts being changed**, **New**, **Modified**, **No
changes** — with the first two open by default, so nothing important hides in a
long list. Each part shows its thumbnail, a badge (**New**, **Draft**,
**Approved**) and a one-line tally, and opens onto every property, BOM row and
file with what would happen: *add*, *replace*, *clear*, *skipped*, *blocked*. A
**JSON report** download captures the whole plan for a colleague.

![The import preview redline showing a new part beside a planned update to an approved part.](/static/help/img/upload-pack-redline.png)

**Blocked** means your choice or your permissions stop that one change. The
import can still proceed; blocked items are left alone.

### Files that do not belong to a part

Only parts listed in the BOM files are created. A deliverable whose name does
not match one of them — CAD temp artefacts are the usual culprit — is **skipped
and reported in the warnings**, never turned into a part of its own.

Warnings like *"Skipped … no BOM entry for …"* are this rule working. Check the
file name if you expected that part to exist.

### Duplicate part numbers

If the same part number and revision appears twice in one pack, the preview
keeps the **first** row, warns that the rows clashed, and offers a chooser. Pick
the row you want and preview again. Nothing is guessed silently.

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

![The Tools page with the add-in, SolidWorks setup, BOM templates and Excel helpers grouped by purpose.](/static/help/img/tools-downloads.png)

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
