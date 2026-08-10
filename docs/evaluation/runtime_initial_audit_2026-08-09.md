# Agent Runtime Initial Audit

Date: 2026-08-09

This audit records the current code-level state of the Runtime migration. It
is an engineering checkpoint, not a production release approval.

## Requirement coverage

| Requirement | Current evidence | Assessment |
| --- | --- | --- |
| Structured goal | `RuntimeGoal`, `RuntimePlan`, goal-intake policy, and registry goal binding | Implemented and covered by Runtime contract/goal tests |
| Executable plan | Versioned `AgentRunPlan` with dependency validation, bounded parallel groups, node budgets, and plan proposals | Implemented; proposal approval remains fail-closed |
| Node-level tools and subagents | `RuntimeHandlerRegistry`, `ToolRegistry`, typed subagent registry, and durable child runs | Implemented for migrated Runtime services |
| Observe-decide-act-verify-replan | `RuntimeController`, `PlanExecutor`, verification history, bounded replan and proposal approval | Implemented; business quality gates are service-specific |
| Durable checkpoint | `AgentRunRepository` and serialized checkpoint trace; checkpoint recovery tests | Implemented; generic control-data preservation was fixed in `b3b6c63` |
| Pause/resume/input/approval/reconciliation | Task control API/service, CAS state versions, one-shot approval, explicit external reconciliation | Implemented and directly regression-tested |
| Observable events | Runtime event bridge, decision/verification events, checkpoint event sequence | Implemented and covered by event/Task boundary tests |
| Reproducible evaluation | Offline trace audit, runtime evaluation cases, canary evaluator, semantic sidecar tooling | Implemented; v2 structural suites bind the private input hash and semantic sidecars are rebound to the same input plus both suite outputs; all release gates remain fail-closed |
| Existing business migration | RESEARCH_01/02/03, TEACH_01/02, Learning controls, General Q&A and Knowledge QA Runtime paths | Provider-free implementation evidence exists; per-Agent release evidence is still incomplete |
| Production authorization | Authorized redacted paired Legacy/Runtime trace, semantic review sidecar, human promotion approval | Not available in the current workspace; must not be synthesized |

## Verification executed in this checkpoint

- Checkpoint/control regression: `10 passed`.
- Business and Runtime contract subset: `43 passed`.
- Runtime core contract, planner, replay, observability, canary, semantic,
  readiness, and release-preflight tests: `122 passed`.
- Task/SSE event ordering, reconnect, Runtime node ordering, plan-proposal
  events, and checkpoint/event correlation: `10 passed`.
- Semantic output-hash binding, canary registry, and release-preflight tests:
  `39 passed`.
- Input-hash v2 collector, structural/semantic binding, canary registry, and
  release-preflight tests: `73 passed` on 2026-08-10.
- Durable child runs, parallel recovery, checkpoint controls, plan proposals,
  subagents, and parallel planning: `29 passed` on 2026-08-10.
- Semantic sidecar collector input-hash validation and intake regressions:
  `44 passed` on 2026-08-10.
- Ruff, targeted Mypy, `scripts/validate_config.py`,
  `scripts/check_sensitive_files.py`, and `git diff --check` passed.
- A broad Windows application-suite run was allowed to run for 364 seconds
  and timed out without a failure report. It is not counted as a passing
  result; slow task-path fixtures should continue to be run separately.

## Authorized development E2E update (2026-08-10)

[The authorized development E2E record](runtime_authorized_dev_e2e_2026-08-10.md)
now captures real, low-volume Legacy/Runtime pairs for
`GENERAL_QUESTION_V1`, `LEARN_01_LOCAL_RETRIEVAL_V1`,
`ACADEMIC_PROBLEM_SOLVER`, and `RESEARCH_01_ACADEMIC_SEARCH_V1`. The isolated
service used real configured non-Xingchen Providers, durable Task/SSE/checkpoint
paths, and one browser-driven workspace submission. Runtime traces used the
actual business plan versions, not the `compat-1` Legacy wrapper.

This evidence is still development-only. It does not include a semantic sidecar
or human promotion decision, so it must not be represented as production canary
or default evidence.

## Release blockers

The provider-free preflight remains intentionally fail-closed when no
authorized artifacts are configured. The current blocking conditions are
missing structural paired-suite evidence and missing semantic evidence. Docker
was not executed. Real non-Xingchen Provider calls were executed only in the
isolated development record above, not in production.

The next release action is to collect a redacted, authorized Legacy/Runtime
pair for each intended Agent/version/plan combination, validate it with the
offline canary packager, collect a separately reviewed semantic sidecar, and
obtain explicit promotion approval before changing launch mode.

## Code-layer conclusion (2026-08-10)

The final targeted core matrix passed `107` tests after the canary v2 protocol
upgrade. Current source and provider-free evidence directly cover structured
goals, executable DAG plans, tool and typed-subagent nodes, the bounded
observe/decide/act/verify/replan loop, durable checkpoints, pause/resume/input,
approval and reconciliation, Task/SSE ordering and reconnect, and offline
evaluation with fail-closed release gates. The frozen SOLVER_CT implementation
was not changed, and the sensitive-file scan passed.

This completes the initial code-layer audit, not the production migration.
The overall objective remains incomplete until structural packaging of the
authorized pairs, independent semantic review, canary observation, and an
explicit default-or-rollback decision are available as auditable evidence.
