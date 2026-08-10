# Non-Xingchen Runtime application E2E (2026-08-10)

## Scope

This record covers the development profile after enabling all currently
registered non-Xingchen business Runtime adapters. RESEARCH_03 is deliberately
excluded from this change and remains an explicit-goal-only path.

The test used the original `/workspace` application entry, not a debug-only
API. The input was a synthesized, non-sensitive academic-search request. The
raw input and full provider payload remain local to the development session;
this document records only redacted observations.

## Configuration verified

`scripts/team_launcher.py start --runtime-dev --force-reload --port 8000`
produced the following effective Runtime posture:

| Agent | Effective launch mode | Runtime plan | Status |
| --- | --- | --- | --- |
| ACADEMIC_PROBLEM_SOLVER | default | solver-runtime-v1 | default_ready |
| GENERAL_QUESTION_V1 | default | general-qa-v1 | default_ready |
| LEARN_01_LOCAL_RETRIEVAL_V1 | default | knowledge-qa-v1 | default_ready |
| TEACH_01_LESSON_PREP_V1 | default | lesson-prep-v1 | default_ready |
| TEACH_02_ASSIGNMENT_REVIEW_V1 | default | assignment-review-v1 | default_ready |
| RESEARCH_01_ACADEMIC_SEARCH_V1 | default | external research Runtime | default_ready |
| RESEARCH_02_ACADEMIC_WRITING_V1 | default | academic-writing-v1 | default_ready |
| RESEARCH_03_DATA_ANALYSIS_V1 | legacy / explicit only | isolated adapter | explicit_goal_only |

The readiness endpoint reported `provider_called=false` for its own
inspection. The application was configured with `requested_provider=mock` and
`active_provider=mock`; no Xingchen workflow was invoked.

## Browser-to-backend acceptance

1. Opened `http://127.0.0.1:8000/workspace` in the existing application.
2. Submitted a redacted academic-search request through the visible input.
3. Observed the application progress sequence: intent recognition, plan
   creation, capability orchestration, external retrieval, answer generation,
   and verification.
4. The result view rendered the research brief, evidence count, evidence IDs,
   source structure, timeline, and external-source disclosure.
5. The Runtime control panel rendered the completed state and terminal control
   protection. The page did not remain stuck in the running state, and the
   input was re-enabled after completion.
6. The browser acceptance found no visible frontend failure in the inspected
   flow. Browser tabs were closed after the check. A browser-console assertion
   was not collected in this run.

Observed external retrieval result: six paper evidence items were rendered by
the application. This is an application observation, not a semantic quality
approval or a release decision.

## Automated verification

```powershell
.\.venv\Scripts\python.exe -m ruff check `
  scripts/team_launcher.py `
  apps/api/app/core/config.py `
  apps/api/app/services/task_runner.py `
  apps/api/tests/test_team_launcher.py

.\.venv\Scripts\python.exe -m mypy `
  --config-file apps/api/pyproject.toml `
  --python-version 3.13 `
  apps/api/app/core/config.py `
  apps/api/app/services/task_runner.py

.\.venv\Scripts\python.exe -m pytest -o addopts='' -q `
  apps/api/tests/test_team_launcher.py::test_runtime_development_profile_enables_non_xingchen_defaults `
  apps/api/tests/test_team_launcher.py::test_runtime_development_profile_rejects_production_and_existing_modes `
  apps/api/tests/test_academic_writing_runtime.py `
  apps/api/tests/test_external_research_runtime.py
```

Result: 14 tests passed; Ruff and Mypy passed. The normal configuration and
sensitive-file checks remain required before commit.

## Boundary and release status

- `SOLVER_CT v1.0` was not modified.
- `research_analysis_runtime.py` and its isolated test file were not modified
  or audited in this change.
- Internal model execution remains mock-backed in the current environment;
  the external retrieval path was exercised through the application.
- This evidence proves application wiring and runtime ownership. It does not
  prove semantic equivalence, production readiness, or authorize a default
  release. Independent semantic review and the human release decision remain
  pending.
