# Contributing guide and branch strategy

These rules apply to every team member. They are part of our SQA plan: they keep
the history traceable to individual members and preserve the test-first (TDD) trail.

## 1. Branches

```
              m1-baseline                              m2-baseline
main     ──────●───────────●───────────────●──────────●──────────   always working, tagged per milestone
                \         /  \            /
feature/...      ●──●────●    ●──●───●───●                          one branch per task, short-lived
```

| Branch | Purpose | Created from | Merged into |
|---|---|---|---|
| `main` | The working project history; each milestone is tagged on it | - | - |
| `feature/<module>-<topic>` | New behaviour, e.g. `feature/intake-guardrails` | `main` | `main` |
| `fix/<topic>` | Defect fixes (link the defect / CAPA id) | `main` | `main` |
| `refactor/<topic>` | Behaviour-preserving restructuring | `main` | `main` |
| `test/<topic>`, `docs/<topic>`, `ci/<topic>` | Tests, documentation, pipeline | `main` | `main` |

Module prefixes: `intake` (Module 1), `research` (Module 2), `planning` (Module 3), `workflow` (Module 4), `kernel` (Module 5).

## 2. Rules for `main`

1. Nobody commits directly to `main`. All changes arrive through a **pull request**.
2. Every pull request needs:
   - at least **one approving review from another team member** (not the author);
   - a **green CI run**: all tests pass, coverage ≥ 60%, pylint ≥ 8.0;
   - a description that names the requirement IDs (from the RTM) it implements or fixes.
3. Merge with **"Create a merge commit"**. Do **not** squash-merge. Squashing would flatten
   the red-green-refactor commit trail that the course grades.
4. Any team member may merge an approved pull request, depending on who is available.
5. Delete the feature branch after merging.

## 3. Test-first (TDD) commit convention

We use [Conventional Commits](https://www.conventionalcommits.org/). Each behaviour is built in this order:

| Step | Commit message example | State of the suite |
|---|---|---|
| Red | `test(planning): add failing tests for budget verdict boundaries (red)` | new tests fail |
| Green | `feat(planning): implement budget verdict classification (green)` | all tests pass |
| Refactor | `refactor(planning): extract cost table from analyzer` | all tests still pass |

Other types: `fix`, `docs`, `ci`, `chore`. Keep commits small and focused on one change.

## 4. Individual attribution

- Commit from **your own GitHub account** with your real name and university e-mail
  (`git config user.name` / `git config user.email`).
- Work mainly in the module you own. Changes to another member's module need that owner's review.
- Contributions made outside Git (reviews, inspections, documents) must leave evidence:
  PR review comments, issue comments or document revision history.

## 5. Baselines

At each milestone any available team member tags the current `main` with an annotated tag:
`m1-baseline`, `m2-baseline`, `v1.0-m3`. A baseline is never changed. Fixes go into the next one.

## 6. Secrets and AI use

- Never commit `.env` or any API key. `.env` is listed in `.gitignore`; use `.env.example` as the template.
- Record every significant use of an AI assistant in the AI Usage Log (tool, purpose, prompt summary,
  what was adopted, what was changed, how it was verified).
