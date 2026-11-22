# Fagan inspection, 21 November 2026

- **Product:** build `m2-baseline` (`cd2433d`), 299 lines of code in three sections (settings and Groq adapter;
  money and keyword routing; facade, workflow nodes and approval form).
- **Basis:** requirements FR-01 to FR-08 and QR-01 to QR-08 (SE431 M1), PEP 8, `inspection_checklist.md`.
- **Meeting:** 21 November 2026, 10:00-12:00 Pakistan time; about 150 lines of code per hour (course slides:
  100-200).
- **Inspection package:** code listing, checklist, defect-log form and the candidate findings of the AI-assisted
  code audit of 15 November (AI Usage Log, entry 12). Every logged defect was checked against the code and agreed
  in the meeting.
- **Stages:** Planning, Overview, Preparation, Inspection meeting, Rework, Follow-up, Exit.

## Timeline (Pakistan time; GitHub shows UTC, five hours earlier)

| When | Event |
|---|---|
| 15 Nov | AI-assisted code audit; its candidate findings go into the inspection package |
| 21 Nov, 10:00-12:00 | Inspection meeting: D-01 to D-08 and their severities agreed |
| 21 Nov, 15:10 | Validation run VAL-01 (end-to-end, sample mode, real Groq LLM) finds D-09 and D-10 |
| 21 Nov, 16:09 | Recorder opens issues #18-#27 |
| 21 Nov, 16:10-16:21 | Rework of D-01 to D-03 (PRs #28, #29, #30; red test first, then the fix) |
| 21 Nov, 20:41-20:47 | Rework of D-04 (PR #33) |
| 21 Nov, after 20:47 | Follow-up: D-01 to D-04 verified; D-09 and D-10 graded Minor |
| 22 Nov | Post-inspection review finds D-11 and D-12 (issues #35, #36) |

## Roles

| Section (author) | Moderator | Reader | Recorder |
|---|---|---|---|
| 1 Muhammad Mehdi Raza | Ahmed Yar Durrani | Mian Muhammad Owais | Ahmed Yar Durrani |
| 2 Mian Muhammad Owais | Ahmed Yar Durrani | Ahmed Yar Durrani | Muhammad Mehdi Raza |
| 3 Ahmed Yar Durrani | Mian Muhammad Owais | Mian Muhammad Owais | Muhammad Mehdi Raza |

Inspectors: Muhammad Bilal (2023392, paired team), Ahmed Yar Durrani, Mian Muhammad Owais, Muhammad Mehdi Raza.

## Defect log

| ID | Issue | Location | Defect | Requirement | Severity | Found by | Author | Status |
|---|---|---|---|---|---|---|---|---|
| D-01 | #18 | `travel_planner/planning/money.py:36` | Money accepts NaN and Infinity as amounts | FR-05, QR-01 | Major | Preparation audit (AI-assisted, 15 Nov); agreed in the meeting | Mian Muhammad Owais | Closed (PR #30) |
| D-02 | #19 | `travel_planner/settings.py:24` | API keys are shown when Settings is printed or logged | QR-04 | Major | Preparation audit (AI-assisted, 15 Nov); agreed in the meeting | Muhammad Mehdi Raza | Closed (PR #28) |
| D-03 | #20 | `travel_planner/llm/groq_adapter.py:52` | Groq SDK retries on its own and has no request time limit | QR-03, QR-02 | Major | Preparation audit (AI-assisted, 15 Nov); agreed in the meeting | Muhammad Mehdi Raza | Closed (PR #29) |
| D-04 | #21 | `travel_planner/workflow/facade.py:62` | Session ID can exceed the VARCHAR(100) thread_id column | FR-08 | Major | Preparation audit (AI-assisted, 15 Nov); agreed in the meeting | Ahmed Yar Durrani | Closed (PR #33) |
| D-05 | #22 | `travel_planner/llm/groq_adapter.py:22` | HTTP 408 and 425 from Groq are treated as permanent errors | QR-03 | Minor | Preparation audit (AI-assisted, 15 Nov); agreed in the meeting | Muhammad Mehdi Raza | Open, M3 Week 11 |
| D-06 | #23 | `travel_planner/intake/routing.py:129` | Keyword routing matches the start of a word, not whole words | FR-02 | Minor | Preparation audit (AI-assisted, 15 Nov); agreed in the meeting | Mian Muhammad Owais | Open, M3 Week 11 |
| D-07 | #24 | `travel_planner/workflow/nodes.py:110` | An empty final plan crashes the session in the finalize step | FR-08, QR-03 | Major | Preparation audit (AI-assisted, 15 Nov); agreed in the meeting | Ahmed Yar Durrani | Open, M3 Week 11 |
| D-08 | #25 | `frontend.py:107` | The error of a refused approval decision disappears at once | QR-06 | Minor | Preparation audit (AI-assisted, 15 Nov); agreed in the meeting | Ahmed Yar Durrani | Open, M3 Week 11 |
| D-09 | #26 | `frontend.py:101` | An approval stores the earlier rejection feedback in the audit log | FR-08, FR-07 | Minor | Validation run VAL-01 (21 Nov, 15:10, after the meeting); graded at follow-up | Ahmed Yar Durrani | Open, M3 Week 11 |
| D-10 | #27 | `travel_planner/workflow/nodes.py:90` | A revision that changes the trip length keeps the old budget | FR-05, FR-07 | Minor | Validation run VAL-01 (21 Nov, 15:10, after the meeting); graded at follow-up | Ahmed Yar Durrani | Open, M3 Week 11 |

## Defects found after the inspection

Found by the post-inspection review of 22 November in code that the inspection covered; logged in the same CAPA
process. Inspection yield: the meeting found 8 of the 12 defects now known in the inspected code (67%).

| ID | Issue | Location | Defect | Requirement | Severity | Found by | Author | Status |
|---|---|---|---|---|---|---|---|---|
| D-11 | #35 | `travel_planner/domain/models.py:147` | An LLM-extracted destination can exceed the VARCHAR(200) destination column | FR-08 | Minor | Post-inspection review (22 Nov) | Muhammad Mehdi Raza | Open, M3 Week 11 |
| D-12 | #36 | `travel_planner/workflow/nodes.py:140` | Saving the approval decision has no error handling | FR-08, QR-03 | Minor | Post-inspection review (22 Nov) | Ahmed Yar Durrani | Open, M3 Week 11 |

## Corrective and preventive actions

| ID | Corrective action | Preventive action | Target |
|---|---|---|---|
| D-01 | Reject non-finite or non-numeric amounts with `ValidationError`; regression test with NaN, Infinity and 'bad' (red, then green) on a `fix/` branch. | Add 'numeric inputs: NaN, Infinity and non-numeric text are rejected' to the code-review checklist. | M2 |
| D-02 | Mark the five secret fields `field(repr=False)`; regression test that `repr(settings)` contains no secret. | Add 'secrets never appear in repr/str/log output' to the code-review checklist. | M2 |
| D-03 | Pass `timeout=30.0` and `max_retries=0`, so `RetryingLLMClient` is the only retry policy; regression test on the SDK options. | Add 'every external call has a time limit and exactly one retry layer' to the code-review checklist. | M2 |
| D-04 | Use `uuid4().hex` (32 characters) as the session ID; regression test with a 100-character user ID. | Add 'generated values fit their database column sizes' to the code-review checklist. | M2 |
| D-05 | Treat 408 and 425 as temporary; regression test (M3 task Q01). | Checklist item: 'error classification is checked against the HTTP status definitions'. | M3 |
| D-06 | Match whole words with a common ending; regression tests (M3 task Q02). | Checklist item: 'text matching is tested with look-alike words'. | M3 |
| D-07 | Create the record inside the guarded block and show the plan with a 'could not be saved' warning; regression test (M3 task Q03). Deferred: it needs an empty LLM answer (rare) and the traveller can retry; accepted by the Team Lead under SQAP 6.3. | Checklist item: 'every value object created from LLM output is inside the error handling'. | M3 |
| D-08 | Re-run the page only when the decision succeeded (M3 task Q04); checked by hand in the app. | Checklist item: 'UI error messages remain visible after the action'. | M3 |
| D-09 | Send feedback only with a rejection (empty text with an approval); manual check in the app (M3). | Checklist item: 'disabled form fields do not submit stale values'. | M3 |
| D-10 | State in the revised itinerary that the budget refers to the original request, or re-run the budget step when the feedback changes the duration (decide in M3). | Checklist item: 'derived results are refreshed when their inputs change'. | M3 |
| D-11 | Limit the destination to 200 characters where `TripConstraints` is built from the LLM answer; regression test with a 201-character destination (M3 Week 11). | Checklist item 7 extended: values that come from LLM output must also fit their column sizes. | M3 |
| D-12 | Catch `PersistenceError` around `record_decision`, log it and continue with a storage warning; regression test with a failing audit log (M3 Week 11). | New checklist item 13: every write to storage is inside the error handling. | M3 |
