# Test and coverage map

263 pytest tests collect across 51 files. Coverage numbers are intentionally absent: the required coverage run did not produce its reports on this host.

Strong unit/integration protection: authentication/security/RLS, API tokens, parts filtering/custom fields, import/upload packs, BOM import/traversal, docpacks/binders, markups, numbering, file materialization and user-facing template smoke tests.

Weak or unprotected areas:

* Flask factory registration, every blueprint/route and every CLI command are not enumerated by an integration route inventory (**dynamic entry point**).
* `docpacks.py` (134,698 bytes), `import_zip.py`, `field_config.py`, `numbering.py`, `parts.py` and `admin_jobs.py` are large; tests cover selected behaviour rather than all error/rollback paths (**missing test**).
* React has lint/build commands but no test command; lint and an external-output production build pass, but the committed production bundle is not source-mapped in pytest (**frontend behaviour**). The build warns about 1.29 MB and 551 kB chunks.
* Shell, Docker, Caddy/Nextcloud and Windows deployment are documentation/manual workflows (**manual/operator workflow**).
* C# has 44 tests but COM registration, SolidWorks event callbacks and installer operation require an installed SolidWorks/manual matrix (**environment-dependent/dynamic entry point**).
* Mongo indexes, persisted setting variants and migrations have indirect coverage only (**critical unprotected behaviour**).

Potential static findings must therefore be classified `UNKNOWN` until route/CLI/template/COM/operator evidence is checked. No coverage gap is itself proof of dead code.
