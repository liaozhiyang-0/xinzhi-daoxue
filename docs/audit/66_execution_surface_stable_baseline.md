# Execution Surface Stable Baseline

Date: 2026-08-25
Branch: `refactor/platform-modernization`

## Baseline state

`RELEASE_BASELINE_COMMIT` remains the user-specified stable baseline:

`5cb699c63bdccdfe454b12d40f399865954d2780`

The post-baseline commits `f1180b6`, `6b5a9c2` and `c0e68cf` were retained as prior work and revalidated with focused tests. Because the current worktree contains substantial uncommitted user changes and the complete manual-release matrix has not been run, no post-baseline commit is promoted automatically.

## Current execution identity

- `BUILD_ID`: `c0e68cf847aa4ccdc38299822932646210f6ee6e-dirty`
- `CONTROL_PLANE_VERSION`: `planner-v1` / active planner mode
- `RUNTIME_GENERATION`: `runtime-v3`
- `CANONICAL_PLAN_VERSION`: `canonical-v1`
- Active planner: `PlannerService`
- Active runtime: `TaskExecutionCoordinator.RuntimeTaskEngine`

## Git publication state

- `FINAL_COMMIT`: not created in this pass.
- `STABLE_TAG`: not created in this pass.
- GitHub push: not performed.
- Working tree: intentionally dirty; previous user work is preserved.

## Remaining READ_ONLY / quarantine surface

Historical task/checkpoint readers, compatibility planners/parsers, old router/workflow/provider code, and legacy plan builders remain in the repository for audit and migration. They are not production construction roots, active registry entries, task retry owners, queue recovery owners, or provider execution fallbacks.

## Release decision

This is an implementation checkpoint, not a final release certification. Promote a new stable commit/tag only after the owner reviews the dirty worktree, runs the missing restart/soak/browser matrices, and explicitly authorizes the Git commit/tag operation.
