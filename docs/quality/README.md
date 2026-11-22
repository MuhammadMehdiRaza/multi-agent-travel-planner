# Quality records

Quality records of the Multi-Agent Travel Planner, kept in the repository as planned in the SE431 M1 SQAP
(section 7.1). The SE431 milestone reports explain them; this folder holds the records themselves.

| File | Content |
|---|---|
| `inspection_2026-11-21.md` | Fagan inspection of the `m2-baseline` build: scope, roles, defect log and CAPA status |
| `inspection_checklist.md` | Code inspection checklist (version 2, with the preventive actions of the M2 inspection) |
| `static_analysis_m2.md` | pylint and radon results of M2 and the triage of every finding |
| `measurements_m2.md` | Measured QR-02 timing, QR-04 secret scan, test counts and coverage of M2 |
| `pylint_m2-baseline.txt`, `pylint_after_SA-01.txt` | Raw pylint output before and after the corrective action |
| `RTM_v2.xlsx` | Requirements Traceability Matrix v2, executed test-design cases, defect log, CAPA status |
| `Risk_Register_v2.xlsx` | Risk register v2 |

Defects are tracked as GitHub issues with the label `inspection-defect` (`post-inspection-review` for defects
found after the inspection); each fix is a `fix/` pull request with a regression test (red, then green) that
closes its issue.
