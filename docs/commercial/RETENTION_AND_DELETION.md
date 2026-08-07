# Data retention and deletion — DRAFT

> Working draft. Review with counsel alongside the privacy policy; retention
> periods interact with statutory obligations that vary by jurisdiction.

## What TinyMRP stores

| Data | Where | Notes |
| --- | --- | --- |
| Parts, revisions, BOMs | MongoDB | The customer's engineering record |
| Engineering files | Deliverables volume | Drawings, models, PDFs, thumbnails |
| Comments and markups | MongoDB | Attributed to a named user |
| Users and roles | MongoDB | Email, hashed password, role assignments |
| Audit log | MongoDB | Who did what, and when |
| Import journal | MongoDB | Import outcomes and rollback records |
| Backups | Backup volume | Database dump plus deliverables snapshot |

## Retention

| Data | Retained | Why |
| --- | --- | --- |
| Engineering data | Life of the agreement | It is the customer's record |
| Audit log | [N] months | Long enough to investigate; short enough not to hoard |
| Import journal | [N] months | Needed to reconcile a failed import |
| Backups | [N] days rolling | Set by `--keep-days`, default 14 |
| Application logs | [N] days | Contain request paths and user identifiers |

## Deletion

**On customer request.** A named user can be removed; their authored comments
and audit entries are retained but the identity is [ANONYMISED / RETAINED —
counsel to decide, this is the clause most likely to conflict with an audit
obligation].

**On termination.** Export supplied within [N] days, deletion within [N] days
after that, backups aged out on their normal cycle within [N] days.

**What deletion does not reach.** Backups already written are not edited. A
record deleted today persists in existing backups until they age out. Say this
plainly rather than implying instant erasure.

## Known gaps as of 2026-08-07

Recorded honestly rather than glossed:

- Backups are **not encrypted**. The owner chose to defer this. Anyone with
  filesystem access to the backup volume can read the customer's engineering
  data.
- Backups are stored **on the same host** as the instance. A host loss takes
  the backups with it.
- Backups **are** checksummed and the restore path has been rehearsed
  successfully, so what exists is known to work.

These should be closed before offering a retention commitment to a customer
who asks how their data is protected.
