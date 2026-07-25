# Repository map

| Component | Purpose / public entry points | Dependencies, persistence and dynamic risk | Tests / risk / owner |
|---|---|---|---|
| `app/__init__.py`, `run.py`, `app/wsgi.py` | Flask factory, WSGI and app startup | Flask-Security, MongoEngine; registers 30+ blueprints, context processors and signal handlers | broad `tests/conftest.py`; **high**; backend platform |
| `app/views/` | server UI, REST APIs and admin views | Flask blueprints, permissions and Jinja/React routes | route/template smoke plus feature tests; **high**; backend UI |
| `app/models/` | MongoEngine documents/embedded documents | MongoDB collections, indexes and model save behaviour | model behaviour is indirectly tested; **critical**; data platform |
| `app/services/` | domain, search, files, docpacks, security and settings | MongoEngine, filesystem, PDF/image libraries; invoked by routes, CLI and model operations | substantial unit coverage but several large modules; **high**; domain teams |
| `app/cli.py` | Click maintenance, seed and import commands | Flask CLI dynamic registration through `init_app` | `test_cli_security`, demos partly manual; **high**; operations |
| `app/templates/`, `app/static/` | Jinja UI, styles, legacy/static assets and built Vite bundle | template names/selectors and static paths are runtime contracts | template smoke only; **high**; frontend |
| `frontend/` | Vite React parts UI | npm/Vite/TypeScript; built output committed under `app/static/parts-ui` | no frontend test script; build/lint only; **medium**; frontend |
| `solidworks-addin/` | COM add-in, exporter, installer | SolidWorks COM callbacks, registry/installer metadata, .NET Framework | 44 tests, 1 local lock failure; **critical**; CAD |
| `docker/`, compose files | container deployment | Docker/nginx and environment configuration | CI build/image scan; **high**; platform |
| `deploy/` | Linux multi-instance, Caddy/Nextcloud, backups and Windows service | operator-facing shell/PowerShell commands, Mongo backups and systemd | documented/manual; **critical**; operations |
| `scripts/`, `tools/` | maintenance, smoke and help generation | manual/operator tooling | manual; **high**; operations |
| `tests/`, `testfiles/` | pytest fixtures and regression suite | mongomock, filesystem/PDF fixtures | 263 collected tests; **medium**; QA |
| `docs/` | help, migration, deployment and architecture records | documents actual operator entry points | manual/documentation; **medium**; product/operations |

Generated/vendor-like directories include `.venv`, `.pytest_cache`, `app/static/parts-ui`, `solidworks-addin/**/bin`, `obj`, and installer executables. They are excluded from deletion decisions unless their generation and deployment paths are independently proved.
