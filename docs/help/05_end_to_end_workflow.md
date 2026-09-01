# Common Workflows

This page provides practical workflows that match current TinyMRP behavior.

## Workflow A: CAD To Production Package

### 1) Prepare CAD data

- Confirm part number and revision in SolidWorks properties.
- Save files before publishing.

### 2) Publish deliverables from add-in

- Use `Publish/BOM` tab.
- Export required model and drawing formats.
- Add associated files if needed.

### 3) Build and import upload pack

- Create upload pack ZIP from the add-in.
- Open **Import** in the web app and choose the ZIP.
- Choose **Add without overwriting** for a partial pack, or **Overwrite with
  the pack** when the ZIP is a complete re-export.
- Press **Preview** and read the redline. Nothing is written yet, and Apply
  stays locked until the preview matches what you are sending.
- Check the warnings: files that do not match a BOM row are skipped and listed
  there.
- Press **Apply** only when the redline matches your intent.

> **Note:** if the redline shows *blocked* rows against an existing approved
> part, that is the approval rule. Either the change is not wanted, or it needs
> someone with `imports.override_approved` to tick “also approved”.

### 4) Validate in Part Detail

- Confirm drawing and 3D preview.
- Confirm expected files and associated files.
- Check attributes and process metadata.

### 5) Generate doc packs

- Use Part Detail `Doc Packs` tab.
- Select outputs for audience:
  - Excel BOM for planning
  - Binder/index/visual for production
  - Hardware summary where needed

## Workflow B: Progressive Ordering Across Multi-Level BOM

This is the key purchasing workflow for complex assemblies. You put a small
number of *roots* on a job, TinyMRP explodes them into every part underneath,
and you then buy that demand in whatever batches suit your suppliers — a
sub-assembly here, a box of brackets there — while the job keeps score.

**The worked example below.** `JOB-2026-014` builds two CELLV03 trailers and one
spare core frame:

| Job BOM root | Rev | Qty | What it is |
| --- | --- | --- | --- |
| `CV03-TR-A01` | A | 2 | Complete trailer |
| `CV03-F01` | A | 1 | Core frame, bought as a spare |

Two lines. But `CV03-F01` also sits *inside* `CV03-TR-A01`, so the frame parts
are required through two different parents, and the job's real demand is 43
part/revision pairs across four BOM levels. That is the situation this workflow
exists for.

### 1) Create job BOM roots

- In `Jobs`, open a job and add BOM lines that represent the job scope.
- Add them by typing `part,revision,quantity` per line, or with Inventory pick
  mode.
- Leave the revision blank to follow the part rather than pin the job to one
  revision. A blank resolves to the most recently updated record for that part
  number, so the job moves with the part when engineering releases a change.
- Roots expand into the full multi-level BOM automatically. You do **not** list
  the children — adding them by hand would double-count the demand.

Quantities multiply down the tree. Two trailers each containing one core frame,
plus one spare frame, makes `CV03-F01` required three times; each `JOIN PLATE`
inside that frame (two per frame) is required six times.

### 2) Review ordering coverage in Job

Open the job and scroll past the BOM editor. There are three purchasing tables,
and each one is the *whole* exploded requirement, not just the roots:

| Table | Shows | Read it when |
| --- | --- | --- |
| `Parts in Orders` | Required vs ordered, with links to the orders | Checking what is already covered and by whom |
| `Over-Ordered Parts` | Quantities ordered above requirement | Reconciling mixed sourcing |
| `Parts Not Yet Ordered` | Outstanding demand, selectable | Raising the next purchase order |

Every row carries the same four numbers:

- **Required** — what the job needs, after multiplying quantities down the tree.
- **Ordered** — what non-draft purchase orders on this job already cover.
- **Remaining** — `Required − Ordered`, floored at zero.
- **Over** — `Ordered − Required` when you have bought more than you need.

### 3) Use `Parts Not Yet Ordered` in Flat or Tree mode

`Flat BOM` aggregates by part and revision: one row per thing you can buy, with
demand from every parent already added together. This is the buying view.

![Parts Not Yet Ordered in Flat BOM mode. Every level of the job is here — the CORE FRAME sub-assembly and the channel and plate parts inside it sit alongside the bought-in hitch and reflectors. CV03-F01 shows 3.00 required: two through the trailers, one as a spare.](/static/help/img/job-ordering-flat.png)

`Tree BOM` splits the same demand back into occurrences and shows where each one
came from. The `Level` column is a path: `+.01` is the first job root, `+.02` the
second, and each further segment steps down one BOM level.

![The same job in Tree BOM mode, filtered to CV03-TR-0. CV03-TR-01 appears twice: 2.00 at level +.01.07.03.01, inside the frame inside the trailers, and 1.00 at +.02.01, inside the spare frame. Those are the two occurrences the Flat view added together into 3.00.](/static/help/img/job-ordering-tree.png)

Use **Flat** to raise orders — it is the quantity you actually buy. Use **Tree**
to answer "why do I need six of these?" before you commit.

Five filters narrow either table: part number, description, revision, level
(tree only) and a minimum remaining quantity. All four text filters match
anywhere in the value and ignore case. Because every level path starts at a job
root, typing `+.02` in `Level` isolates that root's whole subtree — 25 rows in
this example — and `+.01.07.03` narrows to one sub-assembly.

This allows ordering at any level:

- Top-level assemblies
- Intermediate subassemblies
- Leaf components

Rows from different parents can be selected together, so one purchase order can
consolidate the same component wherever it appears in the job.

### 4) Create order from selected remaining parts

1. Filter the remaining table to the group you want to buy.
2. Select rows. The checkbox in the header row selects everything still visible
   under the current filter, so filter first, then select.
3. Click `Create purchase order from selected`.
4. Review and edit the generated order lines.

Two things about the selection are worth knowing. It **survives a change of
filter**, which is how you gather one order from several searches — filter
`HANGER`, select, then filter `CHANNEL`, select again, and both are still
selected when you click the button. It is **cleared by switching Flat and
Tree**, because the two views count the same demand differently and mixing them
would double up the quantities.

![Filtering the description to PLATE and using the header checkbox to take every visible row. Nine rows from three different BOM levels, with the quantities already consolidated — 6.00 of the JOIN PLATE, 2.00 of the registration plate. Check what the filter caught: the ADR Registration Plate Lamp is a light, not plate stock.](/static/help/img/job-ordering-select.png)

The order arrives as a **draft** purchase order against the job, with one line
per selected row, quantity pre-filled to the remaining quantity, and the job's
customer copied across. Nothing is priced yet — set unit prices, adjust
quantities to the supplier's pack sizes, choose the supplier, and save.

![The generated draft purchase order. Each selected row became one line at its remaining quantity; prices and supplier are yours to fill in.](/static/help/img/job-ordering-new-order.png)

The selection is re-checked on the server against the same exploded job
requirement the page rendered. A part that is not in the job's tree, or a
revision you are not cleared to see, is refused rather than silently added.

### 5) Repeat until remaining demand is zero

- Each new non-draft purchase order updates coverage.
- Job rollup recalculates required, ordered, remaining, and over quantities.

A draft order changes nothing. Move it to `submitted` or beyond and the parts
move out of `Parts Not Yet Ordered` and into `Parts in Orders`.

![The same job after the plate order was submitted. The nine parts now sit in Parts in Orders at 0.00 remaining, each linked to PO-2026-001, and the rest of the job continues below in Parts Not Yet Ordered.](/static/help/img/job-ordering-coverage.png)

Repeat with the next commodity group — channel, fasteners, the bought-in running
gear — until the remaining table is empty.

### Who can do this

Creating an order from a job needs `orders.create`; among the shipped roles that
means **Administrator** and **Commercial**. Everyone with `jobs.read` sees the
same tables and the same numbers, so engineering and the workshop can check
coverage without being able to commit spend.

| Role on `JOB-2026-014` | Sees the tables | Rows | `Create purchase order` |
| --- | --- | --- | --- |
| Administrator | Yes | 43 | Yes |
| Commercial | Yes | 41 | Yes |
| Engineering Manager | Yes | 43 | No |
| Engineering, Auditor | Yes | 43 | No |
| Internal, Workshop | Yes | 41 | No |
| Customer (portal) | Their own job | 36 | No |
| Supplier (portal) | Only jobs they have a purchase order on | — | No |

![The same section for a role without orders.create. The tables, filters and Flat/Tree toggle are all there; the button to raise an order is not.](/static/help/img/job-ordering-readonly.png)

The row counts differ because the part scope differs, not because the job does.
Two parts in this dataset are deliberately unapproved, so roles without
`parts.read_unreleased` see 41 rather than 43. The customer sees 36: approval
stops traversal for a portal user, so the unapproved frame also takes with it
the five parts reachable only through it — while the core frame, being a job
root in its own right, keeps its whole subtree visible.

### If a part you expected is missing

1. **It is already covered.** Check `Parts in Orders` before assuming it is
   gone; a part drops out of the remaining table when remaining reaches zero.
2. **A parent was bought.** Ordering an assembly covers everything inside it.
3. **It is unapproved.** Without `parts.read_unreleased` an unapproved revision
   is invisible, and for portal users it also hides everything reachable only
   through it.
4. **It belongs to another job.** Coverage is per job. A part ordered against a
   different job does not count here.
5. **The BOM link is missing.** The job explodes the *part* BOM. If a child is
   absent from the tree, check the parent's BOM tab.

## Understanding Over-Ordered Behavior

Over-order is expected in mixed sourcing scenarios. Example:

1. You order child parts from Supplier A.
2. Later you order the full parent assembly from Supplier B.
3. Child parts can become over-ordered because parent expansion also covers them.

TinyMRP shows these in `Over-Ordered Parts` to make the conflict explicit.

## Order Lifecycle Notes

- Only purchase orders cover a job's requirement. A sales order on the job is
  the customer demand the job exists to fulfil, so it is listed under `Related
  Orders` but never counted as parts already bought.
- `Draft` and `Cancelled` orders are excluded from job ordered coverage.
- Confirmed/delivered quantities drive received progress in job list metrics.

## Scope Of Supply and Customer Deliverables

From Order detail you can download:

- Scope PDF only
- Scope ZIP with attached docs
- Optional children documentation
- Optional combined binder PDF

Use this for supplier or customer transmittals.

## Iteration Loop (Engineering Change)

1. Update model and revision in CAD.
2. Re-publish and re-import deliverables.
3. Re-generate doc packs and scope documents.
4. Re-check jobs/orders coverage where changed items are involved.
