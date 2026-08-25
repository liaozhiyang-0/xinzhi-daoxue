# Active Execution Graph

Date: 2026-08-25
Release baseline under review: `5cb699c63bdccdfe454b12d40f399865954d2780`
Observed working-tree HEAD: `c0e68cf847aa4ccdc38299822932646210f6ee6e`

This graph separates the intended production owner chain from compatibility
objects that are still visible in the current source. The lockdown changes
must make the ACTIVE graph the only constructible and executable production
graph.

## Intended active graph

```text
HTTP / workspace ingress
  -> UnifiedRequestPreparationService
  -> GoalContract validation
  -> deterministic TaskRouter preflight (route evidence only)
  -> PlannerService (single active planner owner)
  -> SkillBindingService / CapabilityBindingRegistry
  -> CanonicalPlan (canonical-v1)
  -> TaskExecutionCoordinator (single task execution owner)
  -> RuntimeTaskEngine / TaskRuntimeLifecycle
  -> RuntimeExecutionBoundary
  -> approved RuntimeBusinessService or declared Runtime handler
  -> RAG / model / tool / Solver capability
  -> result validation / governance / quality gate
  -> TaskCompletionService / ResultCommit / session commit
  -> task events / SSE / workspace presentation
```

## Current call-site evidence

| entry | current observed owner | lockdown decision |
|---|---|---|
| `POST /api/v1/tasks` | `TaskRouter.route` → `TaskCreationService.create_queued` → planner snapshot/canonical plan → `task_executor.submit` | retain one preflight; assert Planner is the only plan owner |
| local task executor | `LocalTaskExecutor` → `TaskExecutionCoordinator` | retain as the only local execution owner |
| Redis task executor | `QueueTaskExecutor` → worker/coordinator path | retain; queue payload must carry generation/build/plan identity |
| retry | `TaskControlService.retry` → new `TaskCreationService.create_queued` | retain only if new task receives current manifest identity and does not reuse legacy executable metadata |
| resume / approve / input | `TaskControlService` changes durable control state → task executor | resume through current Runtime only; historical checkpoint requires compatibility normalization |
| startup recovery | `ApplicationLifecycleResources` → `TaskExecutionCoordinator.recover` → lease manager | add generation and plan/handler validation before requeue |
| Solver | `AcademicSolverRuntimeService` plus existing frozen Solver implementation | preserve capability and freeze its identity; do not create a second Solver chain |
| result path | `TaskRuntimeExecutionService` → `TaskCompletionService` → result/session commit | preserve as the only completion path |

## Owners that must be unique after bootstrap

```text
ACTIVE_PLANNER_OWNER       = PlannerService
ACTIVE_RUNTIME_ENGINE      = TaskExecutionCoordinator -> RuntimeTaskEngine
TASK_EXECUTION_ENTRY       = TaskExecutionCoordinator.execute/submit
TASK_COMPLETION_PATH       = TaskCompletionService.commit
```

`TaskRouter` remains an ingress/preflight component, not a second planner or
execution owner. `OverallRoutingService` and `FallbackRoutingService` are
shadow-only and must not be constructed or injected in production `active`
mode.

## Forbidden edges

```text
active Planner failed       -X-> old Router / legacy workflow
Runtime plan missing        -X-> _build_legacy_plan
handler not active          -X-> provider.default / old provider handler
old checkpoint              -X-> legacy executor
stale queue task            -X-> old Runtime
new Runtime failure         -X-> legacy fallback execution
shadow result               -X-> task route / plan / state mutation
```

The allowed result for every forbidden edge is an explicit, observable
fail-closed error with no provider/tool invocation and no new legacy
checkpoint.

## Preserved capabilities

The lockdown is an execution-surface change, not a feature rollback. The
following remain in scope and must continue to use the active graph:

- Solver semantic workflow and its frozen `SOLVER_CT v1.0` / `SOLVER_CT_V1`
  contracts;
- text and image task input, including multi-image attachment metadata;
- course knowledge RAG, evidence/reference presentation, and formula rendering;
- academic search and external-research result governance;
- multi-turn session context, memory/session summaries and historical display;
- tools, circuit artifacts, verification, governance and SSE presentation;
- local and Redis task execution modes, retries, pause/resume/approval/input;
- runtime checkpoints as data, after normalization into the current Runtime.

## Proof still required

The current repository does not yet prove a frozen registry, a startup
fingerprint, generation fences, a canonical-plan target allowlist, or zero
legacy invocation. These are the next implementation gates. Until they pass,
this graph is an architecture target rather than a release certification.
