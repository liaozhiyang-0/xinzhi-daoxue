# Active Execution Surface

This is the production execution contract for `xinzhi-daoxue`. New features
must attach to this chain; they must not add a second router, planner,
executor, workflow owner or completion path.

## ACTIVE

- `UnifiedRequestPreparationService`
- `GoalContract`
- deterministic ingress preflight (`TaskRouter`, route evidence only)
- `PlannerService`
- `CapabilityBindingRegistry`
- `SkillBindingService`
- `CanonicalPlan` (`canonical-v1`)
- `TaskExecutionCoordinator`
- `RuntimeTaskEngine` / `TaskRuntimeLifecycle`
- `RuntimeExecutionBoundary`
- approved current `RuntimeBusinessService` implementations
- declared `RuntimeSubagentRegistry` and `subagent.*` bindings
- approved `ToolRegistry` tools
- current RAG, external retrieval, model and Solver adapters
- verification, governance and quality gates
- `TaskCompletionService`, result/session commit
- task events, SSE and workspace presentation

## QUARANTINED: NO EXECUTION

- `OverallRoutingService` in production active mode
- `FallbackRoutingService` in production active mode
- `provider.default` generic provider handler
- broad `agent.internal` handler
- `_build_legacy_plan` and `legacy-runtime:*` plan construction
- `RuntimeExecutionBoundary.legacy_provider` execution branch
- `RuntimeLaunchMode.LEGACY` as a production executable outcome
- old Router/Workflow/Provider fallback edges
- historical checkpoint direct resume into a legacy executor

## READ ONLY / COMPATIBILITY

- historical Task, Run, Message, Plan and Checkpoint readers;
- `AgentExecutionPlanner` policy projection until the canonical contract fully
  replaces its persisted policy fields;
- `IntentPlanCompiler` and legacy input/output parsers;
- audit, migration and parity readers.

Read-only compatibility may normalize data for the active Runtime. It may not
call a Provider or Tool, create a new legacy task/run/checkpoint, schedule
work, or mutate active route/plan/result state.

## Ownership rules

```text
ACTIVE_PLANNER_OWNER  = PlannerService
ACTIVE_RUNTIME_ENGINE = TaskExecutionCoordinator -> RuntimeTaskEngine
TASK_EXECUTION_ENTRY  = TaskExecutionCoordinator
TASK_COMPLETION_PATH  = TaskCompletionService
```

Every startup constructs and validates one `ProductionExecutionManifest` and
one startup fingerprint. Registries are frozen after bootstrap. A task,
checkpoint or cache entry that does not match the current runtime generation,
build identity, canonical plan version and handler binding version is rejected
or migrated to the current chain; it is never sent to a legacy executor.
