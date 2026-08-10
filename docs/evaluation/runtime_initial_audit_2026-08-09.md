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
- A later broad non-RESEARCH_03 Runtime/SSE matrix again exceeded the local
  124-second command limit and is likewise not counted as passing. Focused
  terminal-replay/reconnect and Task-to-HTTP-SSE sequence tests passed after
  terminal SSE replay was changed to inspect durable Task state before waiting
  on a disconnect probe. Each focused TestClient fixture still takes roughly
  13 seconds locally, so the remaining broad suite should be sharded in CI.

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

## Observability and static-check refresh (2026-08-10)

Runtime node timing is now derived only from the durable node timestamps and
is exposed consistently through the checkpoint observability projection, the
`plan.node_*` Task/SSE event payload, and the Debug execution event list. The
authorized E2E runner records both a Task lifecycle clock and its client-side
terminal wait clock for future paired sampling; neither field has been used to
rewrite the historical solver parity result.

The follow-up verification passed application Mypy for all 297 source files,
51 focused Runtime/UI tests, configuration validation, sensitive-file scan,
and `git diff --check`. Whole-repository Ruff is intentionally still blocked
by one pre-existing E501 in the frozen, already-committed migration
`20260808_0018_agent_runtime_targets.py`; that migration was deliberately not
rewritten. All currently modified Runtime source and test files pass Ruff.

An attempted fresh local Solver E2E sample did not start because the desktop
execution environment rejected creation of a background API process before a
server or Provider call existed. It is not a test result and does not change
the existing performance or release conclusions.

## Explicit Goal Runtime Task-boundary regression (2026-08-10)

The Task launch policy now resolves the Runtime option key from the business
service selected for the individual request. This preserves the direct business
Runtime as the advertised default while allowing an explicit
`runtime_goal_runtime.execute=true` request to select the wildcard Generic Goal
Runtime instead of silently falling back to Legacy.

The new provider-free TestClient regression submits a structured calculator
goal through `POST /tasks`, waits for its non-blocking Task completion, then
checks the durable Runtime plan (`goal-runtime-v1.r0`), checkpoint-backed Debug
projection, and the persisted `plan.node_started` / `plan.node_completed`
event data used by the SSE/UI contract. The focused Runtime, Task API, SSE
ordering, and Debug UI matrix passed `26` tests. This is integration evidence
only: it uses the read-only calculator tool and makes no external Provider
call, semantic judgment, or release decision.

## Paired-latency attribution refresh (2026-08-10)

To diagnose the Solver's remaining latency variance without weakening the
single-pair fail-closed threshold, Runtime observability now reports both the
sum of completed node work and the wall-clock union of node execution
intervals. `runtime_control_overhead_ms` is the durable Run elapsed time not
covered by that union, so it can expose checkpoint/event/controller overhead
even when nodes run in parallel. The authorized E2E runner copies these values
into its redacted private `report.json`, and the offline paired-sample analyzer
compares them when present. Historical reports simply omit the new fields; no
old result or release decision is rewritten.

## Generic goal capability admission hardening (2026-08-10)

The default Generic Goal Runtime policy now admits only tools that are both
non-side-effecting and not approval-gated. A request goal can select a
privileged tool or subagent only when the routed Agent has an explicit full
handler-ID allowlist. This prevents request-controlled goals from converting a
descriptor's approval requirement into an implicit authority grant; the
existing Runtime approval gate remains the second, durable enforcement layer.

## Core Runtime audit matrix (2026-08-10)

The current provider-free core audit matrix passed `142` tests in 122 seconds.
It covers Runtime contracts, structured-goal planning and intake, Generic Goal
execution/replan, typed subagents, durable checkpoint/replay and parallel
recovery, proposal and control gates, Runtime observability, paired-sample and
semantic/release evidence contracts, Solver parity, and Task/SSE reconnect and
ordering. The matrix deliberately excludes RESEARCH_03-specific tests because
that business path is being handled independently. It does not substitute for
new authorized Provider samples, independent semantic review, or a human
release decision.

## Generic goal Task approval lifecycle (2026-08-10)

The Generic Goal Runtime now re-indexes handler descriptors for each plan
compilation, so an enabled extension registered after the TaskRunner exists is
visible to the next explicitly declared goal. A Task API regression registers
an in-memory approval-gated fixture, grants it only to
`GENERAL_QUESTION_V1`, then proves `Task → waiting_review → /approve → queued
→ Runtime completion` with the final answer and the durable
`approval_required` event projection. This is provider-free integration
coverage; it does not authorize a production extension or replace release
review.

## Scoped approval and deterministic node order (2026-08-10)

Approval grants are now bound to the exact handler scope recorded in the
durable approval audit. When independent nodes are ready in parallel, one
approval can release only its matching handler; other approval-gated nodes
remain ready until a separate approval is recorded. The executor consumes both
the one-shot approval flag and its scope before dispatch. Checkpoints created
before the scope field existed remain recoverable through their recorded
approval decision, but newly submitted approvals always persist an explicit
scope. Runtime node state construction also follows the plan's declared order
rather than an unordered set, making readiness, approval prompts, event order,
and replay behavior deterministic.

### Verification for this control-plane change

- Ruff passed for the changed Runtime, Task-control, and test modules.
- Targeted Mypy passed for `contracts.py`, `executor.py`,
  `task_control_service.py`, and `task_runner.py`.
- The focused Runtime/Task checkpoint, recovery, generic-goal, approval, and
  true-agent matrix suite passed: `47 passed` (two third-party deprecation
  warnings).
- Regression suites excluding the independently-owned RESEARCH_03 path also
  passed: business Runtime services `26 passed`, General Question Runtime
  `11 passed`, and Solver plus Knowledge QA Runtime `16 passed`.
- Configuration validation, sensitive-file scanning, JavaScript syntax, and
  Git diff checks passed. The local configuration requested the mock Provider;
  no Provider call or Docker run occurred.

The combined application-level Task execution-path suite exceeded the local
Windows command window and was not counted as passed. Its dedicated Generic
Goal Task API coverage is included in the focused 47-test suite above.

## Debug projection plan order (2026-08-10)

The execution-debug API now orders durable node rows from the restored
immutable plan instead of the database's lexical node-ID order. This keeps the
operator console aligned with actual planning and execution order even for
identifiers such as `step.10` and `step.2`; unknown legacy rows remain visible
at the end in stable lexical order. Static console/API projection coverage
passed `9` tests and the Generic Goal Task API end-to-end suite passed `2`
tests. The larger SSE/observability combination exceeded the local Windows
command window in this run and is not represented as a new passing result.
