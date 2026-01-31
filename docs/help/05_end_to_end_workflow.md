# End-to-end workflow (golden path)

This is the recommended workflow from design to doc pack.

## Step 1: Set up the server

1) Install the TinyMRP server (see Server installation section).
2) Create the first admin user.
3) Log in as admin and create roles and users.
4) Set branding and timezone in Admin Settings.

**Expected result:** Users can log in and see the Inventory page.

## Step 2: Prepare parts in SolidWorks

1) Open the part or assembly.
2) Confirm the part number and revision in the properties.
3) Save the model.
4) If you use numbering, allocate a number and apply it.

**Common mistake:** Exporting deliverables before the part number is saved.

## Step 3: Publish deliverables

1) Open the Publish/BOM tab in the add-in.
2) Select the outputs you need (PDF, DXF, STEP, 3MF, PLY, STL, PNG).
3) Choose the deliverables folder.
4) Optional: click "Manage associated files..." and add extra files (photos, scans, reports).
5) Optional: enable "Create Upload Pack (ZIP)" if you want a ready-to-upload ZIP.
6) Click Publish.
7) Wait until the process finishes.

**Expected result:** Files appear in the correct deliverables subfolders.

## Step 4: Package for import

1) If you used "Create Upload Pack (ZIP)", use that file.
2) Otherwise, create a ZIP with the correct structure:
   - `deliverables/<group>/...`
   - `bom/` with `*_FLATBOM.txt` and `*_TREEBOM.txt`
   - `extra/<PN>/<REV_OR__no_rev__>/...`
3) Keep file names matching `PARTNUMBER_REV_REVISION.ext`.

**Tip:** If you are unsure, start by zipping one part and verify the import result.

## Step 5: Import into TinyMRP

1) Log in to the web app.
2) Go to Upload Pack.
3) Upload the ZIP file.
4) Wait for the import summary.
5) Open the part detail page to confirm files are visible.

**Expected result:** The part shows files and thumbnails on its detail page.

## Step 6: Generate doc packs

1) On the part detail page, open Doc Packs.
2) Select the outputs you need:
   - Binder (full PDF pack)
   - Index (standalone)
   - Visual summary
   - Hardware summary
   - Excel BOM
3) Click Generate and download the result.

**What this button does:** Generate creates a PDF or ZIP. It does not change your part data.

## Step 7: Extract BOM and reports

1) Use the Excel BOM output to share the BOM.
2) Use the binder and visuals for manufacturing packages.
3) Save outputs to your project folder.

## Iteration loop (when a part changes)

1) Update the model in SolidWorks.
2) Increment the revision if required.
3) Re-export deliverables.
4) Re-import into TinyMRP.
5) Regenerate doc packs.

## If something goes wrong (decision tree)

- **No files appear after import**
  - Check folder names inside the ZIP.
  - Check that file names match the part number and revision.
  - Confirm the deliverables folder is mounted to the server.

- **Wrong revision shown**
  - Confirm the revision in SolidWorks properties.
  - Re-export and re-import.

- **3D preview missing**
  - Confirm a 3MF, PLY, or STL file exists.
  - Check the file name pattern.

- **Doc pack is empty**
  - Ensure PDFs exist for the part.
  - Re-generate after verifying files.

