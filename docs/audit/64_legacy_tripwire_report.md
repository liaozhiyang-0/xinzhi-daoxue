# Legacy Tripwire Report

Date: 2026-08-25

## Tripwires

Production attempts to reach a quarantined provider bridge or forbidden handler emit `LEGACY_EXECUTION_ATTEMPT` with `component`, `caller`, `task_id`, `trace_id`, `build_id`, and `runtime_generation`, then raise `LegacyExecutionForbidden` and fail closed.

The architecture telemetry registry now includes:

- `legacy_runtime_invocation_count`
- `legacy_router_invocation_count`
- `legacy_handler_invocation_count`
- `legacy_plan_creation_count`
- `legacy_checkpoint_execution_count`
- `execution_target_not_active_count`
- `stale_task_rejected_count`
- `compatibility_read_count`
- `startup_fingerprint_mismatch_count`
- `registry_drift_count`
- `shadow_result_mutation_count`

## Evidence

- The first post-restart short question was rejected because the new manifest initially omitted the current per-run `knowledge.qa.*` handlers. It raised `ExecutionSurfaceError` (`handler is not active`) rather than falling back to a legacy path.
- After adding the explicit active handler namespaces, the same current knowledge path completed successfully.
- No `LEGACY_EXECUTION_ATTEMPT`, `LEGACY_EXECUTION_FORBIDDEN`, legacy provider invocation, legacy router invocation, or legacy plan construction was observed in the latest live service log.

## Live development snapshot

The development observability snapshot after the successful browser task reported zero for `legacy_runtime_invocation_count`, `legacy_router_invocation_count`, `legacy_handler_invocation_count`, `legacy_plan_creation_count`, `legacy_checkpoint_execution_count`, `execution_target_not_active_count`, `shadow_result_mutation_count`, `startup_fingerprint_mismatch_count` and `registry_drift_count`. `compatibility_read_count` and `stale_task_rejected_count` were also zero in this sample. This is a point-in-time snapshot, not a long-run certification.
