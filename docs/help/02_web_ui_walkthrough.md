# Web UI walkthrough

This section explains each screen in the web app, what it is for, and how to use it.

## Inventory (Parts list)

**URL:** `/ui/parts`

### Where to find it

- Top navbar: Inventory

### What you can do on this screen

- Search and filter parts.
- See basic metadata (part number, revision, description, category, status).
- Jump to a part detail page.
- Use pick mode when selecting parts for other workflows.

### Step-by-step

1) Open Inventory.
2) Use the search box to type a part number or description.
3) Use filters (if visible) to narrow by process, category, status, or document type.
4) Click a part number to open its detail page.

### What to expect

- The list updates as you search.
- If you have no permissions, the list may be empty.

### Troubleshooting

- **Nothing appears:** Confirm you have at least the "items.view" permission.
- **Search is slow:** Reduce filters or search a smaller term.

## Part detail

**URL:** `/ui/part/:pn`

### Where to find it

- From Inventory, click a part number.

### What you can do on this screen

- See thumbnails and drawings.
- Download deliverables (PDF, DXF, STEP, 3MF, PLY, STL, etc).
- Preview 3D models.
- Generate doc packs.
- Review revision history, where-used, and related jobs/orders.

### Step-by-step: viewing images and drawings

1) Look at the preview image area near the top.
2) If a drawing exists, it appears in the drawing panel.
3) Click the image to view it larger in the browser.

**Tip:** Drawing images are taken from files ending with `_DWG.png`.

### Step-by-step: 3D preview

1) If a 3D file exists, the preview panel is visible.
2) If multiple formats exist, select the format before loading.
3) Use the toolbar:
   - Fit, Reset, Front/Right/Top/Iso views
   - Zoom in and out
   - Toggle Grid, Axes, Edges, Wireframe
   - Toggle Section cut
   - Auto-rotate
   - Full screen
   - Measure (click two points)

**What this button does:** The Measure tool shows the total distance plus X/Y/Z distances between two clicks.

### Step-by-step: downloading files

1) In the file groups section, click a file type (PDF, DXF, STEP, 3MF, PLY, STL).
2) If multiple files exist, choose the one you need.

### Step-by-step: associated files

1) Open the "Associated files" tab.
2) Click "Upload files..." to attach extra files (photos, scans, reports).
3) Use Download to open a file.
4) If you have edit permission, use Delete to remove a file.

**Tip:** Associated files are stored by Part Number + Revision. An empty revision is still valid.

### Step-by-step: generating doc packs

1) Open the Doc Pack panel.
2) Choose the outputs you want (Binder, Index, Visual, Hardware Summary, Excel BOM).
3) Optional: include flat patterns or extra fields if available.
4) Click Generate.
5) Download the result when it is ready.

**Common mistake:** Generating a binder without deliverable PDFs will produce an empty pack. Always ensure PDFs exist first.

### Troubleshooting

- **No 3D preview available:** Confirm a 3MF, PLY, or STL is present.
- **Missing files:** Check that files were exported and imported correctly.

## Dashboard

**URL:** `/ui/dashboard`

### Where to find it

- User menu (top right) > Dashboard

### What you can do on this screen

- See system health statistics and recent updates.
- Get a quick overview of document coverage.

### Step-by-step

1) Open Dashboard.
2) Review the summary tiles and tables.

### Troubleshooting

- **No data:** The system may be new or data import has not run yet.

## BOM views

**URL:** `/ui/bom` and `/ui/bom/:pn`

### Where to find it

- User menu > BOM

### What you can do on this screen

- View a multi-level BOM.
- Expand and collapse assemblies.
- Inspect quantities and part info.

### Step-by-step

1) Open BOM.
2) Search for a top-level part number.
3) Expand rows to see child components.
4) Click a part number to open its detail page.

### Troubleshooting

- **Parts missing:** The BOM may not be imported or linked yet.

## Tokens page (Add-in access)

**URL:** `/ui/addin/tokens`

### Where to find it

- User menu > Tokens

### What you can do on this screen

- Create access tokens for the SolidWorks add-in.
- Copy a token to use in the add-in configuration.
- Revoke tokens when no longer needed.

### Step-by-step

1) Click "Create token".
2) Copy the token and store it securely.
3) Paste it into the SolidWorks add-in configuration.

**Common mistake:** Tokens are shown only once. Copy them immediately.

## Admin add-in page

**URL:** `/ui/admin/addin`

### Where to find it

- Admin Dashboard > Add-in

### What you can do on this screen

- Review add-in settings and token health.
- Monitor add-in usage (if enabled).

### Troubleshooting

- **Access denied:** You must be an admin user.

## Admin Dashboard

**URL:** `/admin` (varies by setup)

### Where to find it

- User menu > Admin Dashboard (admin users only)

### What you can do on this screen

- Manage users and roles.
- Set app branding and timezone.
- View the audit log.

### Step-by-step: branding and timezone

1) Go to Admin Dashboard.
2) Open App Settings.
3) Upload a logo and set the timezone.
4) Save changes.

**What this affects:** The logo appears in the app and doc packs. The timezone controls generated timestamps.

## Import BOM and deliverables

**Recommended:** `/ui/upload-pack`

### Where to find it

- Top navbar: Upload Pack (if you have permission)

### What you can do on this screen

- Upload a ZIP file containing BOM, deliverables, and associated files.
- Trigger a scan and thumbnail build.

### Step-by-step

1) Create a ZIP with the correct folder structure (see End-to-end workflow section).
2) Drag the ZIP into the upload box or click to browse.
3) Wait for the import result message.
4) Open the part detail page to verify files were found.

### Troubleshooting

- **ZIP rejected:** Check the folder structure and file naming.
- **No thumbnails:** Run the thumbnail rebuild command or re-import.

### Legacy BOM import (if needed)

**URL:** `/import/upload`

Use this screen if you only need to import a BOM and do not need to upload deliverables or associated files.

