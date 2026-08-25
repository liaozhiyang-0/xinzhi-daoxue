# Checkpoint / Queue / Generation Report

Date: 2026-08-25

## Current-generation envelope

New tasks persist an `_execution_surface` metadata envelope in the existing task options. It contains:

- `runtime_generation`
- `build_id`
- `planner_version`
- `canonical_plan_version`
- `handler_binding_version`
- `capability_binding_version`
- `startup_fingerprint`

No database migration was added and no historical task or checkpoint was deleted.

## Recovery rules

- Current-generation tasks continue through the current Runtime.
- Tasks without a compatible envelope, or with a stale generation/plan, are marked terminal with `execution_surface_incompatible` during lease recovery.
- Retry creates a new current-generation task through `TaskCreationService`; it does not resume a legacy executor.
- Historical checkpoint reads remain compatibility reads only. They are normalized into current state before execution; unsafe state fails closed.

## Cache fences

Context assembly and RAG result cache keys now include the current generation/build fence. A new build therefore misses route/plan-sensitive cache entries created by an older execution surface.

## Not yet certified

No artificial stale task/checkpoint injection matrix has been run against a disposable test record. The implementation is covered by focused unit tests; the full queue/lease soak remains pending.
