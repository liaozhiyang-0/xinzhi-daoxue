# Phase P Team Handoff

## What is now stable

- Active Planner control plane and CanonicalPlan lineage;
- Non-blocking Task API and durable Runtime/Checkpoint/terminal state;
- six-case catalog, capability/skill metadata and common student HTML workspace;
- AC-01 public demo asset and real upload boundary;
- evidence/publish/manual-review status projections;
- single Markdown/KaTeX rendering path and math fixtures.

## Start locally

```powershell
cd C:\Users\86184\Desktop\xinzhi-daoxue
.\.venv\Scripts\python.exe scripts\validate_scenarios.py
.\.venv\Scripts\python.exe scripts\validate_planner_controlled_takeover.py
.\.venv\Scripts\python.exe scripts\validate_evaluation_cases.py
.\.venv\Scripts\python.exe -m pytest apps\api\tests\test_student_web.py -q --no-cov
```

Backend tests are run from the repository root with the project `.venv`. See `docs/demo/final_demo_runbook.md` for the six-case flow.

## Safe operating rules

1. Do not enable a real Provider without explicit credentials, published Flow/Agent configuration and a bounded budget.
2. Do not call `allow_mock` or a development fallback a real result; the UI must retain provider/mock/fallback provenance.
3. Do not publish TP/LP/KG/AC results without the stated teacher or human-review boundary.
4. Do not restore the retired `SOLVER_CT v1.0` route; use the current `ACADEMIC_PROBLEM_SOLVER` provider and HTTP chain.
5. Do not add another Router, Planner, Runtime, or Markdown/KaTeX renderer.

## Troubleshooting

| Symptom | First check | Safe action |
| --- | --- | --- |
| Case6 image preview fails | `GET /demo-assets/case6-opamp.png` and demo contract | restore static asset route; do not expose admin question-bank route |
| Task waits forever | task events, Runtime status, lease/worker logs | preserve task ID; inspect checkpoint before retry |
| Evidence insufficient | `evidence_status`, `publishable`, `manual_review_required` | add/approve course material; do not force publish |
| Real model unavailable | Provider preflight and configuration | use explicit local/Mock mode and label it |
| Formula display issue | student-page formula checks and math quality fields | keep the single renderer; add fixture before changing rendering |

## Rollback

Rollback must be a reviewed revert of the final release commit on the feature branch. Do not force-push, reset a shared branch, alter migrations, or merge main automatically. Preserve Pilot task IDs and evidence artifacts for diagnosis.

## Ownership after handoff

- Product/demo owner: six-case prompts, screenshots and manual review wording;
- Runtime owner: task lifecycle, SSE, checkpoint, retry/resume/cancel;
- Agent quality owner: Planner capability/skill policy and evidence contracts;
- Provider owner: credentials, model/Flow release, budget and incident logs;
- QA owner: full suite, Final Pilot manifest and release gate.
