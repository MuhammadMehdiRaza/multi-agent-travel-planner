# Code inspection checklist (version 2, 21 November 2026)

One criterion per item. Items 9-12 were added as preventive actions of the M2 inspection (defects D-05 to D-10);
items 3, 4, 5 and 7 were sharpened by D-01 to D-04.

1. Does each unit implement its requirement (FR/QR) completely, including the documented limits?
2. Are untrusted values (user text, environment settings, LLM output) validated where they enter the module?
3. Are numeric inputs protected against NaN, Infinity, non-numeric text and out-of-range values? (D-01)
4. Can any secret (API key, database password) reach a log, an error message, `repr()` or the screen? (D-02)
5. Does every external call have a time limit, and is there exactly one retry layer? (D-03)
6. Are errors converted into the project's own exception types and shown to the user with a reason? (D-08)
7. Do generated values fit the database schema (column sizes, allowed values)? (D-04)
8. Is shared data accessed safely by the concurrent research threads?
9. Are HTTP status codes classified as temporary or permanent according to their definition? (D-05)
10. Is text matching tested with look-alike words? (D-06)
11. Are values created from LLM output inside the error handling? (D-07)
12. Do disabled form fields avoid submitting stale values, and do derived results refresh when their inputs
    change? (D-09, D-10)
