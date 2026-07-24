# Phase 0 baseline

Audit date: 2026-07-25 (Australia/Sydney).  Inspected branch: `main`; inspected commit: `c55fc7015ef19d4c415076f4bc371cdbd2364062` (`approved identification fixes`).  The working tree was clean before the audit.  Audit work is on `cleanup/phase-0-baseline-audit`.

## Environment and installation

| Item | Observed |
|---|---|
| Python | 3.12.4; Python 3.11 was not installed locally (`py -0p` listed only 3.12) |
| .NET SDK | 8.0.204 |
| Node / npm | v20.14.0 / 10.7.0 |
| Dependency method | pinned `requirements.txt` plus `requirements-dev.txt`; existing `.venv` supplied validation tooling |
| C# target | .NET Framework 4.8, x64 |

## Validation results

| Command | Result | Counts / notes |
|---|---|---|
| `python -m pytest --collect-only -q` | pass | 263 collected in 1.60 s; three dependency deprecation warnings |
| `python -m pytest -vv --durations=20` | pass | 263 passed, 280 warnings in 93.22 s. The earlier apparent non-termination was the command runner returning before its child Python process, not a pytest lifecycle defect. |
| `.venv\\Scripts\\python -m pytest -q --cov=app --cov-branch --cov-report=term-missing --cov-report=html --cov-report=json` | pass | 263 passed, 280 warnings in 285.98 s; 61.27% line coverage and 49.78% branch coverage. `htmlcov/` and `coverage.json` were generated locally and not committed. |
| `.venv\\Scripts\\python -m ruff check .` | pass | configured CI rules: all checks passed. |
| `.venv\\Scripts\\python -m ruff check app tests --select F401,F811,F841` | fail (evidence only) | 95 findings: 75 safely autofixable according to Ruff; not applied. |
| `.venv\\Scripts\\python -m black --check .` | fail | 125 files would be reformatted; CI marks this non-blocking. |
| `.venv\\Scripts\\python -m mypy app/services/security_mode.py app/services/api_auth.py` | pass | no issues in the two CI-scoped modules. |
| `.venv\\Scripts\\python -m bandit -r app -ll` | pass | 28,373 LOC scanned; no medium/high issues (275 low findings below threshold). |
| `dotnet build solidworks-addin\\TinyMRP.SolidWorksAddin\\TinyMRP.SolidWorksAddin.csproj -c Release -p:Platform=x64` | pass | 0 warnings, 0 errors. |
| `dotnet test solidworks-addin\\TinyMRP.SolidWorksAddin.Tests\\TinyMRP.SolidWorksAddin.Tests.csproj -c Release -p:Platform=x64 --no-build` | pass twice | 44/44 passed in 4.38 s, then 44/44 passed in 3 s after test-only AppData isolation. |
| ShellCheck / Hadolint | command unavailable | required by CI but not installed on this Windows host. |
| `frontend: npm ci` | pass with warnings | installed 285 packages; Node 20.14.0 is below Vite/plugin declared minimum 20.19.0; audit reported 12 total vulnerabilities. |
| `frontend: npm run lint` | pass | ESLint exited 0. |
| `frontend: npm run build -- --outDir C:\\Temp\\tinymrp-phase0-frontend-build` | pass with warning | 146 modules transformed in 7.65 s; deliberately used an external output directory because normal build empties committed `app/static/parts-ui`; main bundle is 1.29 MB and ThreeMFViewer chunk 551 kB. |
| `frontend: npm audit --omit=dev --audit-level=high` | fail | 2 high vulnerabilities reported through `react-router-dom`/`react-router`; recorded only, no upgrade performed. |
| `vulture app tests --min-confidence 80` | not completed | tool was installed, but the combined runner process did not complete reliably; Ruff findings are the recorded static evidence. |

## Acceptance conclusion

Phase 0 is complete. Python 3.11 remains an external host limitation, precisely evidenced by the installed-interpreter listing; the complete suite and coverage baseline nevertheless pass under the available Python 3.12.4. No production behaviour was changed.
