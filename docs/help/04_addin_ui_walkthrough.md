# SolidWorks add-in walkthrough

This section explains each tab and option in the TinyMRP SolidWorks add-in.

## Publish/BOM tab

### Where to find it

- Open the TinyMRP task pane.
- Click the Publish/BOM tab.

### What you can do

- Export deliverables (PDF, DXF, STEP, 3MF, PLY, STL, PNG).
- Export BOM files.
- Publish for a single model or a whole assembly.

### Step-by-step: publish deliverables

1) Open a part or assembly in SolidWorks.
2) In Publish/BOM, select the outputs you need.
3) Choose the deliverables folder.
4) Click Publish.
5) Wait for the process to complete.

**What this button does:** Publish creates files on disk. It does not automatically upload them; you upload or import them later.

### Associated files (extra files)

1) In Publish/BOM, click "Manage associated files...".
2) Add one or more files (photos, scans, reports).
3) Optional: add a label in the list.
4) Click OK to save.

**What this does:** The list is stored inside the CAD file as a custom property (`TINYMPR_ASSOC_FILES`).

### Create Upload Pack (ZIP)

1) Check "Create Upload Pack (ZIP)" in the Publish/BOM options.
2) Click Publish.
3) The add-in writes a ZIP that contains BOM files, deliverables, and associated files.

**Tip:** If revision is blank, the ZIP uses the `__no_rev__` token in the extra files path.

### Step-by-step: export BOM

1) Open the top-level assembly.
2) Choose BOM options (flat or indented).
3) Click Export BOM.
4) Verify that a BOM file is created in the output folder.

### Troubleshooting

- **Missing output files:** Check that the model is saved and has a part number.
- **Wrong file name:** Check the revision value and part number in properties.

## Tools tab

### What you can do

- Normalize units.
- Hide feature types.
- Run bulk operations on assemblies.

### Tips

- Use Tools carefully on large assemblies.
- Make a backup before running mass changes.

## Numbering tab

### What you can do

- Select a numbering scheme.
- Preview how numbers will look.
- Allocate part numbers to configurations.
- Apply or rename based on rules.

### Step-by-step: allocate part numbers

1) Open the Numbering tab.
2) Pick a scheme from the list.
3) Click Preview to see the next number.
4) Click Allocate to assign to the current configuration.

**Common mistake:** Allocating numbers without saving the document. Always save after allocating.

## Configuration tab

This area controls how the add-in connects to the server.

### Quick Start sub-tab

- Server URL
- Token
- Test connection

### Advanced sub-tab

- Folder locations
- Custom behavior flags
- Debug options (if enabled)

### Step-by-step: update settings

1) Go to Configuration.
2) Update the fields.
3) Click Save.

**Tip:** If the add-in cannot connect, double-check the URL and token.

## Output folders and naming

The add-in writes files to subfolders inside your deliverables folder. Typical examples:

- `deliverables/pdf/`
- `deliverables/step/`
- `deliverables/3mf/`
- `deliverables/ply/`
- `deliverables/stl/`

File naming uses part number and revision:

- `PARTNUMBER_REV_REVISION.ext`

If the revision is blank, the name ends with `_REV_.ext` (this is expected).

