# Registry / Bootstrap Lockdown

Date: 2026-08-25
Branch: `refactor/platform-modernization`
Current HEAD: `c0e68cf847aa4ccdc38299822932646210f6ee6e`

## Implemented controls

- `ProductionExecutionManifest` is built once by the application composition root.
- FastAPI lifespan runs `ExecutionSurfacePreflight` before the application is served.
- Planner, preparation, runtime boundary, lease recovery and cache fences share the same manifest object.
- Runtime handler, subagent and tool registries are frozen after bootstrap. Runtime business services are immutable after construction.
- Active bootstrap constructs `OverallRoutingService` only in explicit shadow mode.
- The production runtime boundary receives `legacy_provider=None`; historical provider bridging remains compatibility-only.
- A startup log records `PRODUCTION_EXECUTION_FINGERPRINT` with build, generation, planner, handler and capability hashes.

## Active ownership checks

| Check | Result |
|---|---|
| Planner owner | `PlannerService` only |
| Runtime owner | `TaskExecutionCoordinator.RuntimeTaskEngine` |
| Canonical plan | `canonical-v1` |
| Runtime generation | `runtime-v3` |
| Registry freeze | passed in live bootstrap |
| Startup fingerprint | `dc773192222132ba32624b5d66315873e216656c24d2da62e5bf7de3ed145b4c` |

## Remaining proof gap

The manifest and fail-closed gates are implemented, but the complete 10-round cold-start matrix and long-running soak are not yet certified. The current release baseline therefore remains provisional.
