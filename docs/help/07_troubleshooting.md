# Troubleshooting

Use this page when behavior does not match expectations.

## Login Or Access Denied

Checks:

- Confirm user can sign in.
- Confirm role includes required permission for the page.
- Confirm user is linked to correct customer/supplier/job if scoped externally.

Common cause:

- Permission exists but row-level scope excludes requested record.

## Inventory Is Empty Or Missing Parts

Checks:

- Remove filters one by one (`Approved`, `Full files`, `Used in job`, search terms).
- Confirm part revisions exist in database.
- For scoped users, verify part is inside allowed jobs/orders/customer/supplier scope.

## Part Detail Missing Files

Checks:

- Confirm file naming includes correct part number and revision.
- Confirm file is in expected deliverables group.
- Run `Actions -> Update files` in Part Detail.
- For assemblies, try recursive file refresh.

## Drawing Or 3D Preview Missing

Drawing:

- Ensure drawing PNG/PDF artifacts exist for the same PN/rev.
- Confirm drawing PNG naming conventions are respected.

3D:

- Ensure at least one of `3mf`, `ply`, `stl` exists for that revision.
- In 3D tab, pick a file from dropdown if multiple are present.

## Associated Files Not Visible

Checks:

- Confirm files were imported in `extra/<PN>/<REV_OR__no_rev__>/...`.
- Confirm revision token (`__no_rev__` for blank rev) is correct.
- Confirm extra files are enabled by system configuration.

## Upload Pack Import Errors

Checks:

- ZIP contains `bom/` plus valid `*_FLATBOM.txt` and `*_TREEBOM.txt`.
- Deliverables are under valid groups (`pdf`, `dxf`, `step`, etc).
- File size and count are within configured limits.
- Paths are not nested unsafely or using blocked patterns.

Actions:

- Download report JSON from results panel.
- Review `errors` and `warnings` with stage/file context.

## Job Ordering Looks Wrong

If `Parts Not Yet Ordered`, `Parts in Orders`, or `Over-Ordered` seem off:

- Check order status. Draft/cancelled orders do not count for ordered coverage.
- Confirm ordered lines use correct PN/rev.
- If ordering both children and full parent assemblies, over-order on children is expected behavior and should appear in `Over-Ordered Parts`.
- Compare Flat vs Tree remaining view to see aggregate vs occurrence-level demand.

## Doc Pack Output Missing Sections

Checks:

- Confirm selected output checkboxes match desired result.
- For binder, confirm options like `binder_add_*` and selected file types.
- Confirm required files exist for included BOM members.
- If flat patterns are missing, verify flat pattern naming/filter settings.

## Add-in Cannot Connect

Checks in add-in Configuration tab:

- Backend URL reachable from workstation.
- Backend URL is the TinyMRP origin only, not `/api` or `/api/numbering`.
- Auth token is a TinyMRP API token, not the web password.
- Auth token is valid and not revoked.
- `Test connection` reports both health and auth as successful.

If still failing:

- Regenerate token in `/ui/addin/tokens`.
- If the instance was recreated, or `SECRET_KEY` / `SECURITY_PASSWORD_SALT` changed, old API tokens will no longer verify. Generate a new raw API token and paste it into the add-in.
- Existing raw API tokens cannot be recovered from the database because only their hash is stored.
- Ask admin to verify token status in `/ui/admin/addin`.

## Numbering Errors In Add-in

Checks:

- Scheme exists and is active.
- Required context fields for selected scheme are populated.
- Validation rules (charset/length/sequence requirement) are satisfied.

Tools:

- Use `Preview` before allocate.
- Use scheme `Validate` in advanced editor.
- For rename, run dry run first.

## Installer Or Add-in Not Showing In SolidWorks

Checks:

- Installer run as admin.
- Add-in enabled in `Tools > Add-Ins` for both Active and Start Up.
- COM registration exists for add-in GUID.

Repair path:

- Re-run installer.
- Run manual `RegAsm` register command if needed.

## What To Collect Before Escalation

Include:

- Exact page or tab where issue occurs.
- Part number and revision.
- Job/order number if applicable.
- Timestamp and user email.
- For upload/import: report JSON.
- For add-in: last run log from `Open last run log`.
