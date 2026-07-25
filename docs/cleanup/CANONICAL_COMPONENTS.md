# Candidate canonical components (no consolidation performed)

| Responsibility | Candidate implementations / callers | Assessment and required proof | Phase |
|---|---|---|---|
| Revision/part number normalisation | `services/part_norm.py`; `part_materialized.normalized_part_revision`; `part_shares.normalize_share_revision`; C# `PartNumberRenameHelper` | live, overlapping semantics; canonical choice provisional; compare blank/revision/Windows filename tests | 2 / 9 |
| Filename generation | `services/filenames.build_output_name`; docpack/file/export code; C# rename helper | Python and C# have different platform duties; intentionally separate until cross-system contract tested | 2 / 9 |
| Timezones/display dates | `timezone_utils`, Flask template filters, docpack rendering | likely canonical Python helper exists; preserve UTC/local and persisted settings tests | 2 |
| File-path/deliverable lookup | `fileserve.py`, `filescan.py`, `app_settings.py`, `extra_files.py`, `docpacks.py` | duplicate-looking path roots have different access/security roles; high risk | 4 |
| Search/query/canonical/custom fields | `part_query.py`, `canonical_fields.py`, `field_config.py`, `views/parts.py` | live duplicate family; canonical choice uncertain; require Mongo query equivalence and index tests | 3 |
| Permissions/RLS/API errors | `acl.py`, `api_auth.py`, route decorators/helper modules | security-sensitive; do not consolidate from text similarity | 10 |
| PDF merge/stamp/thumbnail | `docpacks.py`, `markup_documents.py`, `thumbs*.py`, `filescan.py` | overlapping document pipelines, but separate outputs; require visual/golden tests | 4 |
| Logging/settings/environment | factory, `logging_setup.py`, `security_mode.py`, deployment libraries | aliases and defaults are live compatibility/configuration surfaces | 7 / 8 |
| SolidWorks close/save/title handling | `SolidWorksDocumentHelper`, publisher, rename service and add-in UI | COM callbacks/reflection risk; canonical choice unknown | 9 |
| Deployment logging/errors | shell `lib/common.sh`, `lib/update.sh`, `lib/nextcloud.sh` | shared libraries already exist; preserve scripts as operator entry points | 8 |
