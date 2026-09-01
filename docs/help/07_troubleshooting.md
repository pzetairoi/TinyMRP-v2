# Troubleshooting

Find your symptom, work down the list. Each entry gives the most likely cause
first.

## I cannot see a part that I know exists

1. **Is it a draft?** External accounts see approved parts by default. An
   administrator may grant `parts.read_unreleased` to a named reviewer, but
   that exception only removes the approval barrier: it does not expose another
   company, job, order or supplier line.
2. **Are you a customer or supplier user?** You only see parts reachable from
   your own relationship. Customers follow their contractual job/BOM subtree;
   suppliers follow their own purchase-order lines and descendants. Being
   listed as a job vendor provides job context, not the whole engineering BOM.
3. **Are filters still applied?** Clear the search box *and* every column
   filter. A filter left in one column silently narrows everything.
4. **Are you on the right revision?** Search the part number alone — other
   revisions appear as separate rows.

## The approved badge is wrong

The badge reflects the value worked out when the part was imported or last
saved.

1. Open **Attributes & Notes** and find the approval property. Values such as
   `pending`, `n/a`, `TBC`, `no` or a blank all mean *not approved*.
2. If the source value looks correct but the badge disagrees, the approval
   rules changed after the part was imported. An administrator can run the
   rebuild on **Admin → Fields & exports** to recompute every part.
3. If a part shows approved and you expected draft, check whether an approver
   *name* is present — a valid name counts as approval.

## Files are missing from a part

1. **Check the file name.** Deliverables must be named
   `PARTNUMBER_REV_REVISION.ext` — for example `3950-35_REV_A.pdf`, or
   `3950-35_REV_.pdf` when there is no revision. A drawing image ends `_DWG`.
2. **Check the folder.** The file must sit in the right group folder (`pdf/`,
   `step/`, `png/`…).
3. **Relink them.** Part Details → **Actions → Update files** rescans storage
   for that part. For a whole database, an administrator can use **Admin →
   Rescan files**.
4. **Check your permissions.** Some file categories are permission-gated; you
   may be seeing a filtered list.

## The import created parts I did not expect

Only parts listed in the FLATBOM or TREEBOM are created. If you see unexpected
parts, look at the BOM files themselves.

If instead you expected a part and it is **missing**, check the import
warnings for *"Skipped … no BOM entry for …"*. That means a file's name did not
match any BOM row, so it was skipped rather than inventing a part. CAD temp
artefacts — names containing `.tmp` — are the usual cause and are correctly
ignored.

## The import did nothing / did too much

1. **Check which choice you made.** *Add* never overwrites; *Overwrite* makes
   the part match the pack, removing what the pack does not carry. The advanced
   panel can also have a category set to *Skip*.
2. **Preview first.** The redline lists every intended change before anything is
   written, and Apply only unlocks while that preview still matches.
3. **Look for "blocked".** Blocked rows are changes your choice or permissions
   would not allow — most often an approved part without the “also approved”
   tick.
4. **Check *skipped* against the Reason column.** *Add* deliberately keeps any
   value that is not empty.
5. **A screen full of *clear* rows** means you are overwriting with a partial
   pack: it removes everything it omits. Use *Add* for partial packs. See
   [Import: what each choice does](#import-what-each-choice-does) for the full
   matrix and an exercise that reproduces each case.

## An import says I lack permission

The redline lists required and missing permissions *before* you apply. The
usual ones:

| Missing | Means |
| --- | --- |
| `imports.execute_low_risk` | You may preview but not apply |
| `imports.execute_approved` | The plan overwrites data, or records a release |
| `imports.override_approved` | The plan changes an existing **approved** part (the tick) |

The last is deliberate: creating an approved part is allowed for any uploader,
changing one is not.

## A Doc Pack is missing sections

1. **Depth** — *top level only* excludes children.
2. **Consumed / classified / process filters** may be excluding the parts you
   expect.
3. **The source files must exist.** A binder cannot include a PDF that was
   never uploaded. Check the Files tab first.
4. **Permissions** — you need `exports.run`, `bom.read` and `files.read`.
5. **If none of the above explains it, check the server log.** A pack that loses
   its index or a page stamp now records why. Search for `docpack index could not
   be built` or `could not stamp page`. Before this, those failures were silent
   and the pack simply arrived incomplete.

## A Doc Pack is taking a long time

Full-BOM binders on large assemblies genuinely take minutes. The progress bar
shows what is being prepared. Press **Cancel** to get the page back; you can
narrow the scope and try again.

## Comments or markups are not visible

You need `comments.read` and `markups.read` respectively. If the tab loads but
shows an error about a job, the part may be linked to a deleted job — report it
with the part number so it can be cleaned up.

## Jobs and ordering look wrong

1. Confirm the job BOM matches the part BOM you expect — they are separate, and
   the job BOM is a snapshot you can edit.
2. *Parts not yet ordered* and *over-ordered* compare purchased quantity against
   job requirement. A part ordered against a different job will not count here,
   and neither will the sales order the job is being built for.
3. If children are missing from the tables, check the parts are approved — an
   unapproved revision stops the walk for anyone without
   `parts.read_unreleased`, so its children disappear with it.
4. Financial columns may be blank because you lack `orders.financial.read`,
   not because the data is missing.

## The add-in cannot connect

1. Confirm the server URL, including `http://` or `https://`.
2. Confirm the API token is active and has not expired — token secrets are shown
   once at creation or rotation. Create or rotate one from **My Account → Tokens**
   if unsure, then replace the old secret in the add-in immediately.
3. Confirm the machine can reach the server at all (open the URL in a browser).
4. Check the token has not been revoked by an administrator, account
   deactivation or a password change/reset.

## The browser shows an authentication or CSRF error

   HTTPS URL. Strict cookies are not intended for a plain-HTTP public site.
2. Confirm Caddy still forwards the original host and scheme. A browser write
   is rejected when its Origin/Referer does not match the routed instance.
3. Do not paste an API bearer token into browser requests. Browser-only APIs
   require the signed login session; tokens are for the add-in/integrations.
4. If a page reports `token_required`, check that the frontend is not calling
   the add-in-only `/api/auth/check` endpoint.
5. If an older instance intentionally remains in compat during migration,
   confirm its instance `.env` explicitly says so; updates preserve that value.

## What to collect before asking for help

Include as much of this as you can:

- The **part number and revision**, exactly as shown.
- What you expected, and what happened instead.
- Your **role**, if you know it.
- For import problems, the **JSON report** from the redline — it captures the
  whole plan.
- The time it happened, so an administrator can find it in the audit log.
