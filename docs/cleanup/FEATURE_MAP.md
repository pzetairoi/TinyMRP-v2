# Feature map

| Workflow | Entry point | Main modules / data | Tests / validation | Risk |
|---|---|---|---|---|
| Login, account, roles, tokens | security routes, `/api/auth`, CLI `user`/`role` | `models/auth.py`, `services/acl.py`, `api_auth.py`, `api_tokens.py` | account, ACL, API auth, security tests | critical |
| Admin settings/timezone | admin settings and React admin pages | `views/admin.py`, `services/app_settings.py`, `timezone_utils.py`, `AppSettings` | timezone/settings tests | high |
| Parts/search/multifilters/custom fields | `/api/parts`, React parts UI | `views/parts.py`, `part_query.py`, `canonical_fields.py`, `field_config.py`, `Part` | field/filter/frontend-contract tests | critical |
| Part details/BOM/where-used | part shell/API routes | `parts.py`, `bom_tree.py`, `whereused.py`, `models/bom.py` | BOM/where-used tests | critical |
| Jobs/orders/companies | admin/API routes | `admin_jobs.py`, `admin_orders.py`, customer/supplier models, `order_scope.py` | rollup/RLS/docpack tests | high |
| Import and upload packs | import/upload routes and CLI | `import_zip.py`, `upload_pack.py`, `filescan.py` | import/upload/filescan tests | critical |
| Deliverables/external sharing | file routes and public share routes | `fileserve.py`, `files_access.py`, `extra_files.py`, `part_shares.py` | file source/public download/share tests | critical |
| PDF binders/docpacks/markups | docpack and drawing-markup APIs | `docpacks.py`, `markup_documents.py`, `part_drawing_markups.py` | docpack/markup tests | high |
| Comments/notifications | part and markup APIs | annotations/notifications services and models | comments/notification tests | high |
| SolidWorks export/upload | COM commands/UI | `SwAddin.cs`, publisher, document helper, upload builder | 44 C# tests + live SolidWorks verification | critical |
| Multi-company/update/rollback | documented shell commands | `create-instance.sh`, `update-instance.sh`, `rollback-instance.sh` | manual host/restore drill | critical |
| Nextcloud linking | documented shell commands | `lib/nextcloud.sh`, link/scan/install scripts | manual Docker/Nextcloud validation | critical |
| Windows service | PowerShell installer | `deploy/windows/*.ps1` | manual Windows service/nginx validation | high |

All listed workflows can be configuration-, template-, CLI-, COM- or operator-invoked; absence of direct Python imports is not dead-code evidence.
