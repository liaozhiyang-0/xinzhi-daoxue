# RC-EXEC-01 Release Candidate Identity

Date: 2026-08-26
Repository: `xinzhi-daoxue`
Branch: `refactor/platform-modernization`
Working tree: dirty, 70 entries, no staged changes

## Release identities

| Field | Value |
|---|---|
| `RELEASE_BASELINE_COMMIT` | `5cb699c63bdccdfe454b12d40f399865954d2780` |
| `EXECUTION_LOCKDOWN_CHECKPOINT` | `c0e68cf847aa4ccdc38299822932646210f6ee6e` |
| `BUILD_ID` | `c0e68cf847aa4ccdc38299822932646210f6ee6e-dirty` |
| `CONTROL_PLANE_VERSION` | `planner-v1` |
| `RUNTIME_GENERATION` | `runtime-v3` |
| `CANONICAL_PLAN_VERSION` | `canonical-v1` |
| active planner owner | `PlannerService` |
| active runtime owner | `TaskExecutionCoordinator.RuntimeTaskEngine` |
| active handler hash | `274b47462e100c04fa7f0225baf3d346462514246f5a9bcc5f54c0b152073349` |
| active capability hash | `c6939909e8d1cffe21910c70b3605b6ed26b3491afdcb824e978d321925b8acf` |
| active tool hash | `11cd1c6fe65038a7b4bd11bd3e9dd06a5db705e786dff2805d12acf2125031ac` |
| startup fingerprint | `4cf777dbb274a7f10a2cbcdd24aef9e3e9635d4d8b628016b121e5b29973dc1b` |
| provider mode | local runtime |
| queue mode | local |

## Evidence

- The post-binding service restart emitted the current startup fingerprint:
  `4cf777dbb274a7f10a2cbcdd24aef9e3e9635d4d8b628016b121e5b29973dc1b`.
- The subsequent ten-round cold matrix observed this same fingerprint on all
  30 tasks and all ten architecture snapshots.
- `/api/v1/health` reported `status=ok`, `database=ok`, `redis=ok`,
  `minio=ok`, and `configuration_status=ready`.
- The point-in-time architecture snapshot after restart reported zero for
  legacy runtime/router/handler/plan/checkpoint invocation, execution-target
  rejection, stale-task rejection, shadow mutation, registry drift, and
  fingerprint mismatch.
- The current startup includes `active_tool_hash` in
  `PRODUCTION_EXECUTION_FINGERPRINT`; this was not present in the earlier
  checkpoint and is now part of the RC identity.
- The capability hash changed when the missing academic-writing binding was
  registered. This is why the earlier fingerprint was retired rather than
  reused.

## RC decision

`RC-EXEC-01` is recorded and eligible for A2 testing. It is not yet a Stable
Release: the 10-round cold-start matrix, persisted-state cases, soak, full
browser matrix, and final release gate are still outstanding. No commit or tag
was created.
