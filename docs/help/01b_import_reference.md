# Import: what each choice does

The Import page takes a ZIP produced from CAD and writes three kinds of thing:
**part properties**, the **BOM**, and **files**. You make one choice about how
they are written, plus one tick for approved parts.

This chapter is the detailed reference. The short version is in
[Web UI walkthrough → Import](#import). If you only remember one sentence, make
it this one:

> Nothing is written until you press **Apply**, and the **preview redline is
> exactly what the apply will do** — row by row.

## The two choices

| | New part | Existing **draft** | Existing **approved** |
| --- | --- | --- | --- |
| **Add without overwriting** | Everything in the pack is written | Only what is empty is filled | **Nothing — blocked** |
| **Overwrite with the pack** | Everything is written | The part is made to match the pack | **Nothing — blocked** |
| **Overwrite + “also approved”** | Everything is written | The part is made to match the pack | The part is made to match the pack |

Three things follow from that table:

- **A new part is never protected.** Anyone who may import can create a part
  that arrives complete and already approved. Creating is not overwriting.
- **Add never destroys anything.** It only fills what is empty.
- **Only the tick reaches approved parts.** Without it, every intended change to
  an approved part/revision is reported as *blocked* and the part is left alone.

The tick is only available to roles holding `imports.override_approved`, and
only applies to categories that are actually overwriting.

## “Overwrite” means the pack wins outright

This is the part worth reading twice. Overwriting does not merge the pack on
top of what is stored; it makes the part **match the pack**:

- A property the pack carries with a different value is **replaced**.
- A property the pack carries **empty** is emptied.
- A property the pack **does not carry at all** is **removed** — the redline
  shows it as *clear*.

So a re-export whose CAD template stopped exporting the sheet-metal block does
not leave those numbers behind for ever: they go, and the redline says so before
you apply.

> **Common mistake:** overwriting with a **partial** pack. A pack carrying four
> columns will, under Overwrite, remove everything else on those parts. Packs
> from the add-in's *Create BOM* carry the whole record and are safe. If you
> built a small pack by hand, use **Add**. The preview makes this obvious: a
> screen full of *clear* rows means the pack is not a complete record.

### What is never removed

Some values cannot come back from a CAD pack, so an overwrite never touches
them:

| Kept | Why |
| --- | --- |
| `seed` | Which import created the record |
| `cad_ref`, `numbering_scheme_id` | Written when a part number is allocated in TinyMRP |
| `notes`, `comments` | Annotations written by people here |
| Unit of measure | A part with no UoM is not usable, and no CAD pack omits it |
| The three approval fields | Governed by the approval rule below, not by the property wipe |

Comments, markups, doc packs, jobs and orders are separate records entirely: no
import touches them.

### A part the pack only lists as a child is never emptied

Parts that appear solely in the TREEBOM carry no properties. Overwriting those
would mean that *mentioning* a part as a child wipes it, so it does not happen:
only parts with a real FLATBOM row are rewritten.

## What counts as approved

TinyMRP never sets approval. It is read out of the pack, which is how it gets
here from CAD and PDM.

| In the pack | Result |
| --- | --- |
| `approved`, `is_approved`, `approval_status`, `released` = `yes`, `y`, `true`, `1`, `on`, `approved`, `released` | Approved |
| The same columns = `no`, `n`, `false`, `0`, `off`, `draft`, `none`, `null`, `n/a`, `pending`, `tbc`, `tbd`, `wip`, `rejected`, `-`, blank | Not approved |
| `ApprovedBy`, `approved_by`, `approver`, `released_by` holding a **name** | Approved, by that person |
| Any other text in one of those columns | Treated as an approver's name — so the part counts as **approved** |
| `ApprovedDate`, `approved_date` | Stored as the approval date; a date alone does **not** approve |

**An explicit “no” wins.** A row with `approved = No` and `ApprovedBy = FQ` is a
draft.

**A stray word approves.** Anything the list above does not recognise is read as
an approver's name. If a CAD template writes `checked` into the approved column,
the part imports as approved by "checked". An administrator can add that word to
the unapproved values in **Admin → Fields & exports**.

**Contradictions block instead of guessing.** `approved = Yes` together with
`is_approved = No`, or two different approver names, produces the warning
*“Incoming approval aliases conflict”* and every approval row is blocked, under
every choice.

### Releasing is not overwriting

Because approval comes from CAD, publishing one is new information rather than a
modification:

| Situation | Add | Overwrite | Overwrite + tick |
| --- | --- | --- | --- |
| Draft here, approved in the pack | **Applied** — the part is released | Applied | Applied |
| Approved here, approval unchanged in the pack | Nothing to do | Nothing to do | Nothing to do |
| Approved here, **not** approved in the pack | Blocked | Blocked | **Approval is cleared** |
| Approved here, different approver or date in the pack | Blocked | Blocked | Applied |

> **The trap:** re-exporting a CAD file whose approval properties were never
> written back produces a pack with **empty** approval columns. With the tick on,
> an empty column wins like any other value: the redline shows *Approved*
> changing to No and the approver and date being **cleared**, and the apply does
> exactly that. Step 11 of the exercise below demonstrates it safely.

Approval is written as a whole set, so a pack that re-signs a part with a new
date but the same approver leaves the approver and status exactly as the redline
showed them.

## Properties

“Properties” means the ordinary fields (description, material, finish, mass…),
your custom fields, and the approval fields.

- **Add** writes a field only when the current value is empty. A field that
  already holds anything — even `n/a` — is left alone and reported as *skipped*.
- **Overwrite** replaces what differs and removes what the pack does not carry.
- An incoming value **identical** to the stored one is *unchanged* and does not
  make the part count as changed.

### Column names are not field names

Several source columns map to one logical field. The redline shows the field's
label and, underneath, *from &lt;column&gt;*, so you can see which column won.

| Field | Columns that feed it |
| --- | --- |
| Finish | `finish`, `treatment`, `colour`, `color` |
| Mass | `mass`, `weight` |
| OEM Part Number | `supplier_partnumber`, `supplier_part_number`, `oem_part_number`, `oem_partnumber` |
| Datasheet | `datasheet`, `oem_data_sheet`, `data_sheet`, `datasheet_url` |
| Description | `description`, `desc`, `desc1`, `summary_text` |
| Process | `process`, `process2`, `process3`, `secondprocess`, `thirdprocess` (all kept — Process is multi-value) |

If two of those columns disagree in the same row, the **first one wins** and the
redline says so: *“Conflicting duplicate aliases kept the first value (mass);
ignored: Weight.”* Nothing is lost silently. Overwriting removes **every** column
feeding a field, so a part holding both `treatment` and `finish` loses both when
the pack carries neither.

Administrators can change these mappings in **Admin → Fields & exports**.

### Skip still creates parts when something else needs them

With Properties set to *Skip* in the advanced panel, a BOM row or a file still
needs its part to exist. Those are created as **empty shells** — a part number, a
revision and nothing else.

## BOM

A BOM belongs to one exact **parent part + revision**. `CV03-F01` revision A and
revision B have separate, unrelated BOMs.

- The BOM is written **whole**. There is no merging of single rows: the import
  deletes every row of that parent/revision and writes the pack's.
- **Add** writes a BOM only when the parent has **none at all**. If one exists,
  the redline says *“Fill if empty never merges into an existing BOM”* and lists
  what it would have done.
- **Overwrite** replaces the whole BOM of a draft parent; the tick does the same
  for an approved one.
- Writing a BOM **creates any child that does not exist yet**, so the plan asks
  for `parts.create` as well as `bom.update`.
- Removing a row never deletes the part. It is still in Inventory, just no longer
  used there.
- Quantities are per exact child revision. Swapping REV B for REV C shows as one
  *remove* plus one *add*.

**Common mistake:** the parent/child links come from the dotted **ITEM NO.**
column of the TREEBOM (`1`, `1.1`, `1.1.2`). A TREEBOM numbered `1`, `2`, `3`
parses without error and produces **no links at all** — the parts import, the BOM
stays empty.

## Files

Two kinds of file travel in a pack, and they are identified differently. Neither
is ever deleted for being absent: a pack that carries no files removes none.

### Managed deliverables (`deliverables/<group>/…`)

The groups are `png`, `pdf`, `dxf`, `step`, `edr`, `3mf`, `ply`, `stl` and
`datasheet`, and each only accepts its own file types.

The identity is **part + revision + group + extension + drawing flag** — not the
file name. The file name is only how the importer works out the part, the
revision and whether it is a drawing:

```text
IMPTEST-P01_REV_B.pdf        → IMPTEST-P01, revision B, group pdf
IMPTEST-P01_REV_B_DWG.png    → the drawing image: a SEPARATE identity from the preview PNG
IMPTEST-B02_REV_.png         → a part with NO revision
```

Consequences worth knowing:

- **Everything after `_REV_` is the revision.** `IMPTEST-P01_REV_B_SHEET2.pdf` is
  not a second sheet: it is revision `B_SHEET2`, which no BOM row declares, so it
  is skipped and reported.
- **The part number must match the BOM exactly, including case.**
  `imptest-p01_rev_b.png` does not match `IMPTEST-P01`.
- **A file can be renamed and still be the same identity.** `…_REV_B.PDF` and
  `…_REV_B.pdf` are one PDF: the second replaces the first. The record then
  points at the new name and the old file stays behind in storage, unreferenced.
- Two extensions in the same group are two identities: a part can hold both
  `.eprt` and `.easm` under `edr`.
- **Identical bytes are *unchanged*.** Re-uploading the same file writes nothing.
- A **datasheet** whose name carries no `_REV_` is matched to its part through the
  part's datasheet column instead. If that matches no part it is reported and
  skipped. If it matches several, **every one of them gets a record** — one
  vendor catalogue covering a family of parts is the normal case, and the file
  is stored once under `datasheet/`. Deleting one of those parts with *delete
  files* leaves the catalogue alone until the last part naming it is gone.

### Associated files (`extra/<PN>/<REV>/…`)

Here the identity **is** the stored path, so the file name matters: uploading
`quote-v2.pdf` next to `quote-v1.pdf` adds a second file rather than replacing
the first. An `extra/_manifest.json` can give each one a label. Use `__no_rev__`
as the revision folder for a part with no revision.

### Files never create parts

A deliverable whose name resolves to a part the BOM does not declare is skipped
and reported — *“Skipped … no BOM entry for …”*. This is the rule that keeps CAD
temp artefacts from becoming parts.

### Files already in storage

The add-in's *Create BOM* pack usually contains **only** the two BOM text files;
the deliverables already sit in the storage root. The import scans storage for
every part in the pack and creates or repoints the file records it finds. In the
redline these rows read *found in storage*.

- This runs on **every** import, including re-imports where nothing else changed,
  and including approved parts — pointing a record at bytes that already exist is
  not an overwrite.
- Setting **Files → Skip** in the advanced panel turns the storage scan off.
- It is the same operation as **Part Details → Actions → Update files**.

## Who can do what

Two things are checked: your permission to run an import of that kind, and your
permission to write the resources it touches.

| Permission | Needed for |
| --- | --- |
| `imports.preview` | Previewing at all |
| `imports.execute_low_risk` | Applying a plan that only creates parts and adds data or files |
| `imports.execute_approved` | Applying a plan that **overwrites** anything, or records a release |
| `imports.override_approved` | The “also approved” tick |
| `parts.create`, `parts.update`, `bom.update`, `files.add`, `files.replace` | The writes themselves |

| Role | Preview | Add | Overwrite | Also approved |
| --- | --- | --- | --- | --- |
| **Engineering** | Yes | Yes | Yes | No |
| **Engineering Manager** | Yes | Yes | Yes | Yes |
| **Administrator** | Yes | Yes | Yes | Yes |

Engineering re-publishing its own drafts from CAD is ordinary work, so it needs
no manager. Only approved part/revisions are gated.

The page disables what you cannot use, and the redline lists **Required** and
**Missing** permissions before you apply. An apply you are not allowed to run is
refused whole — it never applies “the parts you were allowed to”.

## Reading the result

**The banner says what happened.** Amber *PREVIEW* means nothing has been
written. Green *IMPORTED* carries the counts — parts created and updated, BOM
rows, files written, file records reconciled — plus the time and the operation
id.

**Apply is only enabled while the preview matches.** Change the ZIP, the choice
or a duplicate pick and Apply switches off until you preview again, because the
redline on screen would no longer describe what an apply would do. If the plan
changes approved parts or removes values, a confirmation step lists both counts
first.

**Parts are grouped by what happens to them**, most demanding first:

| Group | What is in it |
| --- | --- |
| **Blocked** | The policy or your permissions stop these. Applying leaves them alone |
| **Approved parts being changed** | The review list for an override |
| **New parts** | Created by this import |
| **Modified** | Existing drafts this import changes |
| **No changes** | Present in the pack, identical to what is stored |

Blocked and Approved open by default; the rest stay collapsed. Each part shows
its thumbnail, its badge (**New** / **Draft** / **Approved**) and a one-line
tally, and opens onto the row-by-row detail. The thumbnail comes from the pack
itself, so parts that do not exist yet still have a picture.

### What the redline words mean

| Word | Meaning |
| --- | --- |
| **add** | The value, file or BOM did not exist and will be written |
| **replace** | An existing value or file will be overwritten |
| **clear** | A stored property will be **removed** because the pack does not carry it |
| **change** | An approval field will be changed |
| **remove** | A BOM row will disappear |
| **unchanged** | Incoming and stored values are identical |
| **skipped** | The choice made means it is not written (for example Add on a field that already has a value) |
| **blocked** | The choice or your permissions do not allow it — most often an approved target |
| **link** | A file already in storage will be attached to the part |

*Skipped* and *blocked* both mean nothing happens to that row. The difference is
why: *skipped* is your choice working as intended, *blocked* is a protection you
would need the tick, or another permission, to pass.

A plan containing blocked rows can still be applied. Everything else goes through
and the blocked rows are left alone.

## Guided exercise with real test packs

Eleven packs walk one small assembly through engineering, manufacturing,
purchasing, a re-export, release, a new revision and a change request. They are
built from the CV03 sample data, and every part number carries a prefix so
nothing can collide with real parts.

**[Download the practice-pack bundle (.zip)](/help/practice-packs.zip)** — every
step, a README repeating the story below, and the `out_of_band/` files step 8
needs, all in one file. Unzip it; the file names match the table.

Prefer to build it yourself, or want a different prefix? Generate it on any
machine with the repository checked out:

```text
python tools/make_import_test_packs.py
```

That writes the same packs to `testfiles/import_scenarios/`. Add `--prefix
DEMO-` or `--out <folder>` for a different namespace or location.

**Before you start:**

- Run the exercise on a **test instance**, not on production. It really does
  create parts.
- Steps 6, 7, 9 and 11 need the “also approved” tick, so an Engineering Manager
  or Administrator account. Everything else works as Engineering.
- Work through the packs **in order**, and press **Preview changes** before every
  apply. The steps build on each other.

| Step | Pack | Run it as | What to look for |
| --- | --- | --- | --- |
| 1 | `01_engineering_release.zip` | **Add** | 7 new parts, 6 BOM rows, 14 files. Nothing blocked; Engineering can do all of it, and every part shows a thumbnail from the pack |
| 2 | `02_manufacturing_fills_blanks.zip` | **Add** | Lead times are *added*; the new material and description are *skipped* because those fields are not empty |
| 2b | the same pack | preview as **Overwrite**, then go back | A wall of *clear* rows: this pack carries four columns, so overwriting with it would strip the parts. Do not apply it that way |
| 3 | `03_purchasing_supplier_data.zip` | **Add** | Supplier fields fill; the supplier's lead time is skipped because manufacturing already set one; the `.PDF` is skipped because a PDF of that identity exists |
| 4 | `04_full_reexport_overwrite.zip` | **Overwrite** | A complete re-export, so overwriting is safe. Description and mass are replaced; the sheet-metal columns the template stopped exporting are *clear*; cost and lead time arrive empty and are emptied. Engineering can run this without a manager |
| 5 | `05_engineering_release_approved.zip` | **Add** | The release is applied — approving is not overwriting. `IMPTEST-B01` is approved by a name alone; `IMPTEST-A01` stays a draft because it says No |
| 6 | `06_new_revision_line.zip` | **Add**, then Manager with the tick | REV C is created by Engineering. Pointing the approved sub-assembly at it is blocked until the tick |
| 7 | `07_change_request_on_approved.zip` | any, then Manager with the tick | Everything is blocked without the tick. With it, four properties, a PDF and a quantity change go through, and the approval date moves without losing the approver |
| 8 | `08_bom_only_reimport.zip` | **Add** | Copy `out_of_band/` into the deliverables root first. Those two files appear as *found in storage*. Set Files → Skip and they vanish from the plan |
| 9 | `09_bom_restructure.zip` | **Add**, then Manager with the tick | Add refuses to merge. With the tick the old rows are deleted and the pack's three written. `IMPTEST-P02` survives as a part |
| 10 | `10_messy_pack.zip` | **Add**, preview only | A duplicate part number to resolve, three file warnings, an approval conflict and an alias conflict — all reported, none guessed |
| 11 | `11_blank_approval_columns.zip` | preview at all three settings | The trap: only with the tick do the approval rows say *clear*. If you apply it, re-run step 5 with Add to sign the parts again |

**Tip:** after any step, open one of the parts in Inventory and check the value
you expected. The redline and the part must agree.

Clean up afterwards by searching the prefix (`IMPTEST-`) in Inventory.

## Import FAQ

**Does Preview change anything?**
No. It parses the pack, reads the current data and builds the plan. Nothing is
written, no file is stored, no thumbnail is generated.

**Why can I not press Apply?**
Because the preview on screen no longer matches what you would send: the ZIP, the
choice or a duplicate pick changed. Preview again and Apply comes back.

**I chose Add and nothing happened. Why?**
Either the values already existed (*skipped*) or the targets are approved
(*blocked*). Switch the redline to *All rows* and read the Reason column.

**What is the difference between skipped and blocked?**
*Skipped* is your choice not to write. *Blocked* is a protection: the tick, or
another permission, would be needed.

**Will Overwrite delete data the pack does not mention?**
On the parts the pack describes, yes — that is what it means. The preview lists
every removal as a *clear* row first. Parts the pack only lists as BOM children
are not touched, and TinyMRP's own values (part-number allocation, notes) are
never removed.

**I overwrote with a small hand-made pack and lost properties.**
That is the partial-pack trap. Overwrite only with a complete export; use Add for
anything partial. Re-import a full pack to put the values back.

**Can I import only the BOM, or only the files?**
Yes — set the other categories to *Skip* in the advanced panel. Parts still get
created as empty shells if the BOM or a file needs them.

**Can someone without the tick create an approved part?**
Yes, and that is deliberate. Producing approved output from CAD is normal work.
Changing an approved part that already exists is the restricted act.

**Can approval be set inside TinyMRP?**
No. It only ever arrives in a pack. That is why the pack's approval columns
matter so much.

**Will an import ever un-approve a part?**
Only with the “also approved” tick, and only if the pack's approval columns say
so — including when they are blank. The redline shows it as *clear* first. See
step 11.

**Why is my file not attached to the part?**
Check the name against `PARTNUMBER_REV_REVISION.ext`, including the
capitalisation of the part number, and check it is in the right group folder.
Then look in the warnings for *“no BOM entry for …”*.

**The old file is still in storage after a replace.**
Yes. Replacing writes the new file and repoints the record; a file whose name
changed is not deleted from disk. Clean those up in storage if they bother you.

**Does re-importing the same pack twice do damage?**
No. Identical values are *unchanged*, identical bytes are *unchanged*, and the
BOM is rewritten to the same content. The response also tells you the pack was
already imported, with the earlier operation's id.

**A part number appears twice in the pack.**
SolidWorks exports virtual components as `PN^parent`, and several can collapse
onto one part number. The preview keeps the first row, warns, and offers a
chooser; pick one and preview again.

**How big can a pack be?**
By default up to 1024 MB of pack and 5000 files, but the web request itself is
capped at 200 MB unless an administrator raises it. Treat 200 MB as the practical
limit for one upload.

**Can I undo an import?**
Not as a single action. Preview is the safety net, and the confirmation step
counts what will be removed. If an import fails halfway, the parts it created are
removed automatically, the page says whether anything was kept, and what cannot
be undone is recorded for an administrator.

**Can I get the old values back after an overwrite?**
Not through the import. Download the JSON report of the **preview** before
applying: it carries the before value of every row.

**Where do I see what an import did afterwards?**
The banner carries the counts and the operation id, and **Download JSON report**
saves the whole plan. Every run is written to the import journal, which an
administrator can read at `/api/import/operations` — failures first.
