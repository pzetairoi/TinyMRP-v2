# Import: what each policy does

The Import page takes a ZIP from the add-in and writes three different kinds of
thing: **part properties**, the **BOM**, and **files**. Each of those has its
own policy, and approval cuts across all three.

This chapter is the detailed reference. The short version is in
[Web UI walkthrough → Import](#import). If you only remember one sentence, make
it this one:

> Nothing is written until you press **Apply**, and the **preview redline is
> exactly what the apply will do** — row by row.

## The four levels, side by side

Every policy has the same four levels. What they mean depends on the target,
which is always one exact **part number + revision**:

| Level | New part | Existing **draft** part | Existing **approved** part |
| --- | --- | --- | --- |
| **Skip** | Nothing in that category is written | Nothing | Nothing |
| **Fill only** | Everything in the pack is written | Only what is empty is filled | **Nothing — blocked** |
| **Update drafts** | Everything is written | Filled *and* replaced | **Nothing — blocked** |
| **Override approved** | Everything is written | Filled *and* replaced | Filled *and* replaced |

Three facts follow from that table and are worth stating on their own:

- **A new part is never protected.** Any uploader may create a part that
  arrives complete and already approved. Creating is not overriding.
- **Fill only and Update drafts differ only on data that already exists.** On a
  greenfield import they do exactly the same thing.
- **Only Override approved touches an approved part.** Every other level
  reports the intended change as *blocked* and leaves the part alone.

**Tip:** the preset buttons set Properties, BOM and Files together. Change one
in *Advanced* and the preset switches to *Custom* — which is fine and often
what you want (for example Properties = *Fill only* with Files = *Update
drafts*).

## What counts as approved

Approval is not a separate button; it is read out of the pack's columns.

| In the pack | Result |
| --- | --- |
| `approved`, `is_approved`, `approval_status`, `released` = `yes`, `y`, `true`, `1`, `on`, `approved`, `released` | Approved |
| The same columns = `no`, `n`, `false`, `0`, `off`, `draft`, `none`, `null`, `n/a`, `pending`, `tbc`, `tbd`, `wip`, `rejected`, `work in progress`, `-`, blank | Not approved |
| `ApprovedBy`, `approved_by`, `approver`, `released_by` holding a **name** | Approved, by that person |
| Any other text in one of those columns | Treated as an approver's name — so the part counts as **approved** |
| `ApprovedDate`, `approved_date` | Stored as the approval date; a date alone does **not** approve |

**An explicit "no" wins.** A row with `approved = No` and `ApprovedBy = FQ` is a
draft.

**A stray word approves.** Anything the list above does not recognise is read as
an approver's name. If your CAD template writes something like `checked` into
the approved column, the part will import as approved by "checked". An
administrator can add that word to the unapproved values in
**Admin → Fields & exports**.

**Contradictions block instead of guessing.** `approved = Yes` together with
`is_approved = No`, or two different approver names, produces the warning
*"Incoming approval aliases conflict"* and every approval row is blocked, under
every policy.

### Approval follows the Properties policy

The page has no separate approval selector. Approval is written with the
properties:

| Properties policy | What happens to approval |
| --- | --- |
| **Skip** | Approval fields are not written at all |
| **Fill only** | Existing approval is preserved — the rows read *skipped* |
| **Update drafts** | Approval is applied to draft parts; blocked on approved ones |
| **Override approved** | The pack's approval wins, including a blank one |

That last row is the one that surprises people, so it has its own callout:

> **Common mistake:** re-exporting a CAD file whose approval properties were
> never written back produces a pack with **empty** approval columns. Under
> *Fill only* and *Update drafts* that is harmless. Under **Override approved**
> an empty column wins like any other value: the redline shows *Approved*
> changing to No and the approver and date being **cleared**, and the apply
> does exactly that. Step 10 of the exercise below demonstrates it safely.

Approval is written as a set. If the pack re-signs a part with a new date but
the same approver, the approver and status stay exactly as the redline showed
them.

## Properties

"Properties" means the ordinary fields (description, material, finish, mass…),
your custom fields, and the approval fields.

- **Fill only** writes a field when the current value is empty. A field that
  already holds anything — even `n/a` — is left alone and reported as
  *skipped*.
- **Update drafts** also replaces non-empty values, but only on draft parts.
- An incoming value **identical** to the stored one is *unchanged* and does not
  make the part count as changed.
- Blank incoming values are still values on a **new** part: the field is
  created empty.

### Column names are not field names

Several source columns map to the same logical field. The redline shows the
field's label and, underneath, *from &lt;column&gt;* so you can see which column
won.

| Field | Columns that feed it |
| --- | --- |
| Finish | `finish`, `treatment`, `colour`, `color` |
| Mass | `mass`, `weight` |
| OEM Part Number | `supplier_partnumber`, `supplier_part_number`, `oem_part_number`, `oem_partnumber` |
| Datasheet | `datasheet`, `oem_data_sheet`, `data_sheet`, `datasheet_url` |
| Description | `description`, `desc`, `desc1`, `summary_text` |
| Process | `process`, `process2`, `process3`, `secondprocess`, `thirdprocess` (all kept — Process is multi-value) |

If two of those columns disagree in the same row, the **first one wins** and
the redline says so: *"Conflicting duplicate aliases kept the first value
(mass); ignored: Weight."* Nothing is lost silently.

Administrators can change these mappings in **Admin → Fields & exports**.

### Skip still creates parts when something else needs them

With Properties = *Skip*, a BOM row or a file still needs its part to exist. The
import creates those as **empty shells** — a part number, a revision and
nothing else. That is intentional: the BOM cannot point at a part that is not
there.

## BOM

A BOM belongs to one exact **parent part + revision**. `CV03-F01` revision A and
revision B have separate, unrelated BOMs.

- The BOM is written **whole**. There is no merging of single rows: the import
  deletes every row of that parent/revision and writes the pack's rows.
- **Fill only** writes a BOM only when the parent has **none at all**. If one
  exists, the redline says *"Fill if empty never merges into an existing BOM"*
  and lists what it would have done.
- **Update drafts** replaces the whole BOM of a draft parent. **Override
  approved** does the same for an approved parent.
- Writing a BOM **creates any child that does not exist yet**, so the plan asks
  for `parts.create` as well as `bom.update`.
- Removing a row from a BOM never deletes the part itself. It is still in
  Inventory, just no longer used there.
- Quantities are per exact child revision. Swapping REV B for REV C shows as one
  *remove* plus one *add*, not as a change.

**Common mistake:** the parent/child links come from the dotted **ITEM NO.**
column of the TREEBOM (`1`, `1.1`, `1.1.2`). A TREEBOM numbered `1`, `2`, `3`
parses without error and produces **no links at all** — the parts import, the
BOM stays empty.

## Files

Two kinds of file travel in a pack, and they are identified differently.

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

- **Everything after `_REV_` is the revision.** `IMPTEST-P01_REV_B_SHEET2.pdf`
  is not a second sheet: it is revision `B_SHEET2`, which no BOM row declares,
  so it is skipped and reported.
- **The part number must match the BOM exactly, including case.**
  `imptest-p01_rev_b.png` does not match `IMPTEST-P01`.
- **A file can be renamed and still be the same identity.** `…_REV_B.PDF` and
  `…_REV_B.pdf` are one PDF: the second one *replaces* the first. The record
  then points at the new name and the old file stays behind in storage,
  unreferenced.
- Two different extensions in the same group are two identities: a part can
  hold both `.eprt` and `.easm` under `edr`.
- **Identical bytes are *unchanged*.** Re-uploading the same file writes
  nothing.
- A **datasheet** whose name carries no `_REV_` is matched to its part through
  the part's datasheet column instead. If that matches no part, or more than
  one, it is reported and skipped.

### Associated files (`extra/<PN>/<REV>/…`)

Here the identity **is** the stored path, so the file name matters: uploading
`quote-v2.pdf` next to `quote-v1.pdf` adds a second file rather than replacing
the first. An `extra/_manifest.json` can give each one a label.

Use `__no_rev__` as the revision folder for a part that has no revision.

### Files never create parts

A deliverable whose name resolves to a part the BOM does not declare is skipped
and reported — *"Skipped … no BOM entry for …"*. This is the rule that keeps CAD
temp artefacts from becoming parts.

### Files already in storage

The add-in's *Create BOM* pack usually contains **only** the two BOM text files;
the deliverables are already in the storage root. The import scans storage for
every part in the pack and creates or repoints the file records it finds. In the
redline these rows read *found in storage*.

- This runs on **every** import, including re-imports where nothing else
  changed, and including approved parts — pointing a record at bytes that
  already exist is not an overwrite.
- Setting **Files = Skip** turns the storage scan off entirely.
- It is the same operation as **Part Details → Actions → Update files**.

## Who can run which import

Two different things are checked: your permission to run an import of that
risk level, and your permission to write the resources it touches.

| Permission | Needed for |
| --- | --- |
| `imports.preview` | Previewing at all |
| `imports.execute_low_risk` | Applying a plan that only creates parts and adds data or files |
| `imports.execute_approved` | Applying a plan that **replaces** anything, even on a draft |
| `imports.override_approved` | Applying a plan that changes an existing **approved** part |
| `parts.create`, `parts.update`, `bom.update`, `files.add`, `files.replace` | The writes themselves |

**Note the naming:** `imports.execute_approved` is what *Update drafts* needs,
even though no approved part is involved. It is the "this import replaces data"
tier. Overriding an approved part needs `imports.override_approved` **as well**.

| Role | Can preview | Fill only | Update drafts | Override approved |
| --- | --- | --- | --- | --- |
| **Engineering** | Yes | Yes | No | No |
| **Engineering Manager** | Yes | Yes | Yes | Yes |
| **Administrator** | Yes | Yes | Yes | Yes |

The page disables the levels you cannot use, and the redline lists **Required**
and **Missing** permissions before you apply. An apply you are not allowed to
run is refused whole — it never applies "the parts you were allowed to".

## What the redline words mean

Each part is one foldable row with a badge — **New**, **Draft** or **Approved** —
and inside it, three sections: Properties, Files, BOM.

| Word | Meaning |
| --- | --- |
| **add** | The value, file or BOM did not exist and will be written |
| **replace** | An existing value or file will be overwritten |
| **change** / **clear** | An approval field will be changed, or emptied |
| **remove** | A BOM row will disappear |
| **unchanged** | Incoming and stored values are identical |
| **skipped** | The policy chose not to write it (for example Fill only on a field that already has a value) |
| **blocked** | The policy or your permissions do not allow it — most often an approved target |
| **link** | A file already in storage will be attached to the part |

*Skipped* and *blocked* both mean "nothing happens to this row". The difference
is why: *skipped* is the policy working as chosen, *blocked* is a protection you
would need a higher level or another permission to pass.

A plan containing blocked rows can still be applied. Everything else in it goes
through and the blocked rows are left alone. The **Blocked** and **Modified
approved** tabs are the review lists.

## Guided exercise with real test packs

Ten packs walk one small assembly through engineering, manufacturing,
purchasing, release and a change request. They are built from the CV03 sample
data, and every part number carries a prefix so nothing can collide with real
data.

Generate them on any machine with the repository checked out:

```text
python tools/make_import_test_packs.py
```

They appear in `testfiles/import_scenarios/`, with a README repeating each step.
Add `--prefix DEMO-` or `--out <folder>` if you want a different namespace or
location.

**Before you start:**

- Run the exercise on a **test instance**, not on production. It really does
  create parts.
- You need two accounts to see the whole thing: one with the **Engineering**
  role and one with **Engineering Manager** (or Administrator). Anything above
  *Fill only* needs the manager — that is steps 2b, the second run of 3, 4, 5,
  6, 8 and 10.
- Work through the packs **in order**, and press **Preview changes** before
  every apply. The steps build on each other.

| Step | Pack | Run it as | What to look for |
| --- | --- | --- | --- |
| 1 | `01_engineering_release.zip` | Engineering, **Fill only** | 7 new parts, 6 BOM rows, 14 files. Nothing is blocked; Engineering can do all of it |
| 2 | `02_manufacturing_fills_blanks.zip` | Engineering, **Fill only** | Lead times are *added*; the new material and description are *skipped* — those fields are not empty |
| 2b | the same pack | Manager, **Update drafts** | The same rows now say *replace*. As Engineering the Apply button is refused: missing `imports.execute_approved` |
| 3 | `03_purchasing_supplier_data.zip` | **Fill only**, then **Update drafts** | Supplier fields fill; the supplier's lead time is skipped because manufacturing already set one; the `.PDF` replaces the `.pdf` only on the second run |
| 4 | `04_engineering_release_approved.zip` | **Fill only**, then **Update drafts** | Fill only leaves approval alone (*skipped*). Update drafts signs the parts. `IMPTEST-B01` is approved by a name alone; `IMPTEST-A01` stays a draft because it says No |
| 5 | `05_new_revision_line.zip` | Engineering **Fill only**, then Manager **Override** | REV C is created by Engineering. Pointing the approved sub-assembly at it is blocked until the override |
| 6 | `06_change_request_on_approved.zip` | Any level, then **Override** | Everything is blocked below Override. With it, four properties, a PDF and a quantity change go through, and the approval date moves without losing the approver |
| 7 | `07_bom_only_reimport.zip` | **Fill only** | Copy `out_of_band/` into the deliverables root first. The two files appear as *found in storage*. Set Files = Skip and they disappear from the plan |
| 8 | `08_bom_restructure.zip` | **Fill only**, then **Override** | Fill only refuses to merge. Override deletes the old rows and writes the new ones. `IMPTEST-P02` survives as a part |
| 9 | `09_messy_pack.zip` | **Fill only**, preview only | A duplicate part number to resolve, three file warnings, an approval conflict and an alias conflict — all reported, none guessed |
| 10 | `10_blank_approval_columns.zip` | Preview at all three levels | The trap: only under Override do the approval rows say *clear*. If you apply it, re-run step 4 with Update drafts to sign the parts again |

**Tip:** after any step, open one of the parts in Inventory and check the value
you expected. The redline and the part must agree.

Clean up afterwards by searching the prefix (`IMPTEST-`) in Inventory.

## Import FAQ

**Does Preview change anything?**
No. It parses the pack, reads the current data and builds the plan. Nothing is
written, no file is stored, no thumbnail is generated.

**I applied with Fill only and nothing happened. Why?**
Either the values already existed (*skipped*) or the targets are approved
(*blocked*). Switch the redline to *All rows* and read the Reason column.

**What is the difference between skipped and blocked?**
*Skipped* is your policy choosing not to write. *Blocked* is a protection: a
higher level, or another permission, would be needed.

**Can I import only the BOM, or only the files?**
Yes. Set the other policies to *Skip*. Parts still get created as empty shells
if the BOM or a file needs them.

**Why does "Update drafts" ask for a permission with "approved" in its name?**
`imports.execute_approved` is the tier for imports that replace existing data,
whatever its state. Changing an actually-approved part additionally needs
`imports.override_approved`.

**Can someone without the override create an approved part?**
Yes, and that is deliberate. Producing approved engineering output is normal
work. Changing an approved part that already exists is the restricted act.

**Will an import ever un-approve a part?**
Only under **Override approved**, and only if the pack's approval columns say
so — including when they are blank. The redline shows it as *clear* before you
apply. See step 10 of the exercise.

**I changed the approval date and the part became a draft.**
That was a defect, fixed on 2026-08-15. The apply now stores exactly the
approval the redline shows. If you have a part in that state, re-import it with
its approval columns filled, using Update drafts.

**Why is my file not attached to the part?**
Check the name against `PARTNUMBER_REV_REVISION.ext`, including capitalisation
of the part number, and check it is in the right group folder. Then look in the
warnings for *"no BOM entry for …"*.

**I renamed a PDF and now there are two files.**
For managed deliverables there should be one per identity — if you see two,
they differ in extension (`.stp` vs `.step`) or in the `_DWG` flag. For
associated files in `extra/`, a new name always means a new file.

**The old file is still in storage after a replace.**
Yes. Replacing writes the new file and repoints the record; a file whose name
changed is not deleted from disk. Clean those up in storage if they bother you.

**Does re-importing the same pack twice do damage?**
No. Identical values are *unchanged*, identical bytes are *unchanged*, and the
BOM is rewritten to the same content. The response also tells you the pack was
already imported, with the earlier operation's id.

**Why do file records get touched when nothing else changed?**
Because a BOM-only pack reconciles file records from storage every time. That is
how deliverables produced outside an import get attached.

**A part number appears twice in the pack.**
SolidWorks exports virtual components as `PN^parent`, and several can collapse
onto one part number. The preview asks which row to keep; choose and preview
again. Without a choice the first row wins and the pack still imports.

**How big can a pack be?**
By default up to 1024 MB of pack, 5000 files. But the web request itself is
capped at 200 MB unless an administrator raises it, so treat 200 MB as the
practical limit for one upload.

**Can I undo an import?**
Not as a single action. Preview is the safety net. If an import fails halfway,
the parts it created are removed automatically, the page tells you whether
anything was kept, and whatever cannot be undone is recorded for an
administrator to reconcile.

**Where do I see what an import did afterwards?**
The redline stays on screen after applying, and **Download JSON report** saves
the whole plan. Every run is also written to the import journal, which an
administrator can read at `/api/import/operations` — failures first, since
those are the ones needing action.

**Can I still get at an approved part's old values after an override?**
Not through the import. Overriding writes in place. If you need the old state,
download the JSON report of the *preview* first: it carries the before value of
every row.
