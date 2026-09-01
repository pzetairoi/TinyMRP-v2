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

This is the key purchasing workflow for complex assemblies.

### 1) Create job BOM roots

- In `Jobs`, define BOM lines that represent the job scope.
- Roots can expand into full multi-level BOM via server rollup logic.

### 2) Review ordering coverage in Job

In Job detail you have three purchasing views:

- `Parts in Orders`: required vs ordered by part.
- `Over-Ordered Parts`: quantities ordered above required.
- `Parts Not Yet Ordered`: remaining demand.

### 3) Use `Parts Not Yet Ordered` in Flat or Tree mode

- `Flat BOM` view: aggregated by part/revision.
- `Tree BOM` view: per occurrence with BOM level path.
- Toggle between modes depending on purchasing strategy.

This allows ordering:

- Top-level assemblies
- Intermediate subassemblies
- Leaf components

Rows from different parents can be selected together, so one purchase order can
consolidate the same component wherever it appears in the job.

### 4) Create order from selected remaining parts

1. Filter remaining table.
2. Select rows (supports select-all on visible rows).
3. Click `Create purchase order from selected`.
4. Review and edit the generated order lines.

The selection is re-checked on the server against the same exploded job
requirement the page rendered. A part that is not in the job's tree, or a
revision you are not cleared to see, is refused rather than silently added.

### 5) Repeat until remaining demand is zero

- Each new non-draft purchase order updates coverage.
- Job rollup recalculates required, ordered, remaining, and over quantities.

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
