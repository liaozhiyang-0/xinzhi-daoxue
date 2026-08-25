# Legacy Quarantine Inventory

Date: 2026-08-25
Repository: `xinzhi-daoxue`
Branch: `refactor/platform-modernization`
Observed HEAD: `c0e68cf847aa4ccdc38299822932646210f6ee6e`

This is an evidence-based inventory before the execution-surface changes. It
does not delete or rewrite historical code. `can_execute` describes the
current observed capability, not the desired post-lockdown state.

| component | file | historical_role | current_role | importers / constructed_by | callable_from | can_execute | can_write_state | quarantine_action |
|---|---|---|---|---|---|---:|---:|---|
| `TaskRouter` | `apps/api/app/agents/router.py` | legacy route owner in the pre-Planner architecture | deterministic ingress/preflight projection; not allowed to own Runtime execution | constructed in `apps/api/app/main.py`; used by task API, Supervisor and RAG debug | `POST /api/v1/tasks`, Supervisor/debug paths | Yes, route selection only | No direct Runtime state write | Retain as deterministic preflight support; bind its output to the active Planner and add an owner assertion |
| `PlannerService` | `apps/api/app/services/planner.py` | replacement Planner introduced during migration | active Planner owner | constructed/configured by `main.py`; invoked by `TaskCreationService` | task creation | Yes | Yes, through task metadata/events | Mark as the only active planner owner; add manifest validation |
| `OverallRoutingService` | `apps/api/app/services/overall_routing.py` | compatibility/overall router | shadow-only route observation; currently still constructed during active bootstrap | constructed by `main.py`; injected into `build_runtime_task_engine` | `RuntimeRequestPreparationService` when shadow | Yes when injected | It can rewrite task route envelope | Do not construct or inject in active mode; preserve only for explicit isolated shadow tests |
| `FallbackRoutingService` | `apps/api/app/services/fallback_routing.py` | provider/route fallback | shadow-only compatibility path | constructed by `build_runtime_task_engine` only for shadow mode | `RuntimeRequestPreparationService` when shadow | Yes when injected | It can rewrite route/context | No active construction or registration; fail closed if an active request reaches it |
| `AgentExecutionPlanner` | `apps/api/app/services/agent_runtime.py` | old Agent execution-policy dialect | compatibility projection used to materialize RAG/input/timeout policy | constructed by `RuntimeRequestPreparationService` | Runtime preparation | No provider call; produces policy | No | Keep as read-only policy adapter until its fields are fully represented by the canonical contract; never use it for route ownership or fallback |
| `IntentPlanCompiler` | `apps/api/app/services/intent_plan.py` | prior intent plan dialect | compatibility projection for event/API/result consumers | constructed by task creation and Runtime preparation | task creation / route refinement | No direct provider call | Plan/event metadata | Keep read-only; validate that active Runtime uses the canonical plan as authority |
| `RuntimeBusinessRegistry` | `apps/api/app/services/runtime_business_registry.py` | Runtime migration registry | active business Runtime resolver | constructed by `RuntimeExecutionBoundary` from current business services | `TaskRuntimePreparationService`, Runtime boundary | Yes | Through Runtime services | Add manifest allowlist and freeze after bootstrap |
| `RuntimeHandlerRegistry` | `apps/api/app/runtime/handler_registry.py` | generic declarative handler registry | active handler dispatch registry | constructed by `build_runtime_handler_registry` and by isolated Runtime services | `PlanExecutor`, skill binding, generic goal Runtime | Yes | Handler-dependent | Add active allowlist, forbidden-id check and freeze; no mutation after bootstrap |
| `provider.default` handler | `apps/api/app/infrastructure/runtime_adapters.py` | compatibility provider adapter | generic provider execution fallback | registered by `build_runtime_handler_registry`; reachable through a Runtime node | `PlanExecutor` / generic plans | Yes | Provider/result checkpoint state | Quarantine from production manifests; legacy invocation must raise `LegacyExecutionForbidden` |
| `agent.internal` handler | `apps/api/app/infrastructure/runtime_adapters.py` | broad internal-agent adapter | compatibility handler when no declared subagent registry is supplied | `build_runtime_handler_registry` only without subagent registry | generic PlanExecutor | Yes | Runtime checkpoint | Keep only in isolated compatibility construction; production must use declared `subagent.*` bindings |
| `subagent.*` handlers | `apps/api/app/infrastructure/runtime_adapters.py` | explicit current Runtime subagent bindings | active handler adapters for declared local Agents | built from `RuntimeSubagentRegistry` in `main.py` | canonical Runtime plan | Yes | Child-run/checkpoint state | Active only when manifest-declared; freeze registry and validate version |
| `_build_legacy_plan` | `apps/api/app/services/runtime_run_lifecycle.py` | durable envelope for unmigrated Agents | direct legacy Runtime plan constructor | called by `RuntimeRunLifecycleService.start` and `TaskRuntimePreparationService` | task preparation / legacy resume | Yes | Creates Run/checkpoint state | Remove active callers; keep a historical reader/migration-only helper that cannot construct executable plans |
| `legacy-runtime:*` branch | `apps/api/app/services/task_runtime_preparation.py` | compatibility execution for Agents without Runtime plans | active fallback when no business plan resolves | direct call to `_build_legacy_plan` | Runtime preparation | Yes | Creates Run and checkpoint | Replace with fail-closed `RUNTIME_PLAN_NOT_ACTIVE` in production |
| `legacy_provider` branch | `apps/api/app/services/runtime_execution_boundary.py` | old Provider execution bridge | direct execution when a legacy plan is restored | injected by `build_runtime_task_engine` and called by boundary | Runtime execution | Yes | Completes node/checkpoint | Do not inject in active mode; tripwire and fail closed |
| `RuntimeLaunchMode.LEGACY` | `apps/api/app/services/runtime_launch_policy.py` | migration fallback launch mode | returned when release evidence or Runtime mode is missing | `RuntimeLaunchPolicy.resolve` | Runtime preparation | Yes through old path | Runtime/task state | In production convert to explicit launch rejection; never map to an executable legacy plan |
| `OverallRoutingService` rewrite telemetry | `apps/api/app/services/overall_routing.py` | shadow parity observation | route mutation counter | invoked only by compatibility routing | shadow route | Indirectly | Can affect request envelope | Counter may remain; mutation must be impossible in active mode |
| `WorkflowOutputParserRegistry` | `apps/api/app/services/agent_runtime.py` | old workflow output compatibility | parser compatibility layer | constructed by workflow/Agent runtime code | legacy result parsing | Potentially, if old caller reaches it | May shape result metadata | Read-only parser only; add tripwire if invoked from active execution |
| `graph_factory` / frozen Solver graph | `apps/api/app/orchestrator/graph_factory.py`, `apps/api/app/agents/solver_ct/` | existing Solver workflow | preserved current Solver capability and frozen baseline | constructed by `main.py` and Solver Runtime | `ACADEMIC_PROBLEM_SOLVER` Runtime | Yes | Result/artifact state | Preserve; do not modify `SOLVER_CT v1.0` / `SOLVER_CT_V1`; bind only through active manifest |
| `GraphCheckpointer` | `apps/api/app/main.py` and graph modules | historical graph checkpoint mechanism | current Solver compatibility/checkpoint support | constructed by `main.py` | Solver graph | Yes, depending on graph path | Checkpoint state | Read historical state only where the current Solver contract accepts it; never resume a legacy executor |
| task lease recovery | `apps/api/app/application/tasks/leases.py` | task queue/restart recovery | active recovery mechanism without generation validation | `ApplicationLifecycleResources` → coordinator | startup and queue recovery | Yes | Requeues tasks and leases | Add generation/plan/handler validation before requeue; stale tasks migrate or terminal-fail |
| `RuntimeRequestPreparationService` | `apps/api/app/services/runtime_request_preparation.py` | compatibility route/context bridge | active preparation support | `RuntimeExecutionBoundary` | Runtime preparation | Yes, through context/policy and shadow fields | Persists checkpoint snapshot via caller | Disable legacy router/fallback inputs in active mode; invalid resume envelope must fail closed |
| historical `Task` / `AgentRun` / checkpoint rows | DB models/repositories | historical execution data | read/display compatibility data | repositories and task query APIs | history display, retry/resume APIs | Not by themselves | Read-only; retry currently creates a new task | Validate generation; retry must always create current-generation task; old Run cannot resume an old executable graph |

## Classification summary

- **ACTIVE**: `PlannerService`, current `RuntimeBusinessRegistry` services,
  declared `subagent.*` handlers, approved tools, current Solver Runtime,
  result/verification/commit/SSE pipeline.
- **READ_ONLY_COMPAT**: `TaskRouter` preflight projection,
  `AgentExecutionPlanner` policy projection, `IntentPlanCompiler`, historical
  parsers/readers and historical task projections.
- **SHADOW_OBSERVATION**: `OverallRoutingService`,
  `FallbackRoutingService`, parity/route rewrite telemetry.
- **QUARANTINED**: `provider.default`, `agent.internal` broad adapter,
  `legacy-runtime:*` construction, `legacy_provider` execution, and
  `RuntimeLaunchMode.LEGACY` as an executable outcome.
- **REMOVE_CANDIDATE**: only after importer count, construction count and
  production invocation telemetry remain zero for a stability period. This
  phase does not remove files.

## Evidence gaps to close

The repository currently has no single manifest, no runtime generation on
Task/Run/checkpoint envelopes, no startup fingerprint, and no frozen-registry
assertion. Those are implementation gaps, not evidence that the old paths are
already safe. They are addressed by the lockdown work following this report.
