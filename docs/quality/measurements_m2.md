# Measurements, Milestone 2 (22 November 2026)

Measured on the branch of PR #38, which is `main` (`d9f4dad`) plus the evidence tests.
Python 3.13.1, pytest, coverage.py (branch coverage on, as configured in `pyproject.toml`).

## Tests and coverage (QR-05)

Command (the same as CI): `python -m pytest --cov=travel_planner --cov-fail-under=60`

| Measure | Result |
|---|---|
| Automated tests | 396 passed (379 unit, 17 integration), 0 failed |
| Statements in `travel_planner` | 1478 of 1516 (97.5%) |
| Branches in `travel_planner` | 298 of 314 (94.9%) |
| Combined statement and branch coverage | 1776 of 1830 (97.0%) |
| Lowest module | `workflow/postgres_store.py` 89% (its `psycopg` error path needs a real PostgreSQL server) |

## QR-02: research time against the slowest agent (TC-PERF-01)

Test: `tests/unit/test_research_coordinator.py::test_research_takes_at_most_1_5_times_the_slowest_agent`, run in
CI on every push. Three simulated agents of 0.30, 0.20 and 0.25 seconds; ratio = research time / 0.30 s;
target at most 1.5 (one after another the ratio would be 2.5).

Recorded run (`pytest -s -k 1_5`):

```
QR-02 ratios: 1.005 1.005 1.004 1.004 1.002 1.004 1.004 1.003 1.005 1.006; worst 1.006
1 passed
```

## QR-04: secret scan of the whole Git history

Command, run on a full clone with all branches:

```
git log -p --all --no-color | grep -cE 'gsk_[A-Za-z0-9]{20,}|tvly-[A-Za-z0-9-]{10,}|(api_?key|apikey|appid|token|secret)["'\'']?\s*[:=]\s*["'\'']?[A-Za-z0-9]{24,}|postgres(ql)?://[^:/ ]+:[^@ ]+@'
git log --all --oneline -- .env
```

| Measure | Result |
|---|---|
| Commits scanned | 108 |
| Pattern matches | 3, all placeholders: the test value `postgresql://u:pw@h/db` in `test_settings.py`, the local default `postgresql://postgres:postgres@localhost` in `.env.example`, and `postgresql://postgres:<password>@...` in the README |
| Real API keys or passwords found | 0 |
| Commits that touch `.env` | 0 |
