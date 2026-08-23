# Security risk-acceptance template

Use an exception only when a blocking security finding is demonstrably outside
the deployed feature set or no safe remediation exists yet. A named human owner
must approve it; repository prose alone never suppresses a CI gate.

## Rules

1. Prefer a fixed version or configuration change whenever one is available.
2. Give every exception an owner, approval date and expiry of no more than 90
   days unless a shorter period is required.
3. State the exact applicability evidence and compensating controls.
4. Define the condition that immediately voids the exception.
5. Re-run the relevant audit at expiry. Upgrade instead of renewing when a safe
   fix exists.
6. Keep accepted records with the release/change evidence used by the project;
   do not publish vulnerability narratives in end-user Help.

## Record

```text
ID:
Finding/advisory:
Affected component and version:
Severity and blocking gate:
Status: Proposed | Accepted | Expired | Withdrawn
Owner:
Approved on:
Expires:

Applicability:
Why immediate remediation is unavailable:
Compensating controls:
Voiding conditions:
Re-check and removal plan:
Evidence links (CI run, SBOM, audit artifact, change/release record):
```

Expired or unsupported records are release blockers until remediated or
explicitly re-approved. Never use a broad ignore to cover findings outside the
named record.
