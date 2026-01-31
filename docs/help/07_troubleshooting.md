# Troubleshooting

Use this section when something is not working as expected.

## Login issues

- **Cannot log in:** Check email and password. Ask an admin to reset your password.
- **Access denied:** You may not have the required role or permission.

## Missing files in part detail

- Confirm the file is in the deliverables folder.
- Confirm the file name matches the part number and revision.
- Re-import the ZIP.

## Thumbnails not showing

- Wait a few seconds after import (thumbnails are generated).
- If still missing, re-import or run thumbnail rebuild.

## Drawing preview is blank

- Confirm a file ending with `_DWG.png` exists in the `png` folder.
- Ensure the drawing file is readable (open it outside TinyMRP).

## 3D preview missing

- Confirm a 3MF, PLY, or STL file exists.
- Confirm the file name matches the part number and revision.
- Try selecting a different format in the 3D preview selector.

## Doc pack is empty or missing sections

- Ensure PDFs exist for the part.
- Re-generate the doc pack after verifying files.

## Import errors

- **ZIP rejected:** Check the folder structure.
- **No parts created:** Ensure the BOM file and deliverables exist.
- **Wrong revision:** Check the revision value in file names.

## Add-in connection failed

- Check the server URL and token.
- Ensure the server is running.
- Ask your admin to create a new token.

## When to contact support

- You see repeated errors after following the steps above.
- The server does not start.
- Data appears corrupted or missing across multiple parts.

