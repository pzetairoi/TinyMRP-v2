# Cleanup phase status

| Phase | Name | Status | Prerequisites / risks | Candidate count | Required tests | Authorised |
|---|---|---|---|---:|---|---|
| 0 | Baseline and repository audit | completed with validation limitations | coverage runner and C# lock recorded | 18 | collection, static/C#/available checks | yes |
| 1 | Low-risk static cleanup | pending | confirm affected dynamic registrations; no broad autofix | 6 proposed | focused pytest + Ruff F401/F811/F841 | no |
| 2 | Shared primitive consolidation | pending | behavioural equivalence contracts | 0 | timezone/filename/revision tests | no |
| 3 | Search and filter consolidation | pending | query/index and RLS equivalence | 0 | filter/query integration | no |
| 4 | File and document services | pending | filesystem/PDF visual regressions | 0 | docpack/file tests | no |
| 5 | Domain services | pending | Mongo persistence/BOM equivalence | 0 | domain integration | no |
| 6 | Routes/templates/frontend | pending | route/template/selector contracts | 0 | UI/manual/browser | no |
| 7 | Configuration/dependencies | pending | deployment/config compatibility inventory | 0 | clean install/config matrix | no |
| 8 | Deployment systems | pending | operator rollback and host testing | 0 | ShellCheck/manual restore | no |
| 9 | SolidWorks add-in | pending | COM callback/installer proof | 0 | C# + SolidWorks matrix | no |
| 10 | Security/final architecture | pending | all prior phases | 0 | full regression/security | no |

Recommended Phase 1 scope, if authorised: only 6 evidence-backed, import/local/test candidates: `app/__init__.py` redundant import/binding after factory smoke; one or two model unused imports per focused test group; `field_config.py` unused import; and three unused test locals. No Click, route, document, model-field, dependency, template, frontend, deployment or C# changes. Re-run exact focused tests and the unused-rule scan after every small batch.
