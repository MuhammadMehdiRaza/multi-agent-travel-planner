# Static analysis, Milestone 2

- **Tools:** pylint 4.1.2 (configuration in `pyproject.toml`: line length 110, `missing-module-docstring` and
  `too-few-public-methods` disabled, `tests` ignored) and radon (cyclomatic complexity, maintainability index).
- **Command (as in CI):** `pylint travel_planner weather_mcp_server.py`; `frontend.py` analysed separately.

| Measure | `m2-baseline` (`cd2433d`) | After SA-01 (`8add9cb`) |
|---|---|---|
| pylint score, CI scope | 9.24 | 9.33 |
| pylint score, `frontend.py` | 9.44 | 9.67 |
| pylint findings, CI scope | 114 | 101 |
| Errors and warnings | 0 | 0 |
| Average cyclomatic complexity | A (2.43) | A (2.43) |

| ID | Finding | Count | Triage | Action |
|---|---|---|---|---|
| SA-01 | C0301 line-too-long | 13 (+2 in `frontend.py`) | Fixed | PR #31, 0 left |
| SA-02 | C0115/C0116 missing class/function docstring | 48 + 44 | Deferred to M3 | Added with the final design documentation (task Q13) |
| SA-03 | R0902, R0913, R0917, R0911 design warnings | 9 | Justified | Immutable data holders, constructor injection and early returns, see the SE431 M2 report |

Highest complexity: `frontend.show_snapshot` (C, 11) and `ResearchCoordinator.run` (B, 9): refactored in M3
(tasks Q08 and Q06).
