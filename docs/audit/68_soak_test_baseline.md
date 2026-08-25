# 8h Soak Test Baseline

Date: 2026-08-26
This is the pre-soak baseline required by the `xinzhi_8h_soak_boundary_quality_v1`
instruction set. The 8h run is intentionally not started before Release A and
Release B are complete.

## Stable execution identity to carry into the final soak

```text
RELEASE_BASELINE_COMMIT = 5cb699c63bdccdfe454b12d40f399865954d2780
EXECUTION_LOCKDOWN_CHECKPOINT = c0e68cf847aa4ccdc38299822932646210f6ee6e
BUILD_ID = c0e68cf847aa4ccdc38299822932646210f6ee6e-dirty
RUNTIME_GENERATION = runtime-v3
CANONICAL_PLAN_VERSION = canonical-v1
CONTROL_PLANE_VERSION = planner-v1
ACTIVE_PLANNER_OWNER = PlannerService
ACTIVE_RUNTIME_OWNER = TaskExecutionCoordinator.RuntimeTaskEngine
STARTUP_FINGERPRINT = d718d3f3de80ccc36b13687b5dc29664f55da23ddde778c1e7d03f2216c32f96
ACTIVE_HANDLER_HASH = 1b2e9cd67a3be90088c8d045bdfd002a3025c2b9fca2c169cff838a8fba13b82
ACTIVE_CAPABILITY_HASH = ec99d2de6fd0509bd21f4d972e14a8c45ab232ea4e181e5296a4eabb2c57e906
ACTIVE_TOOL_HASH = 11cd1c6fe65038a7b4bd11bd3e9dd06a5db705e786dff2805d12acf2125031ac
```

## Golden Set to freeze before the final soak

```text
General 10
CT 15
AE 10
DE 10
SS 10
RAG 10
single image 10
multi-image 10
Circuit 20
long sessions 5
```

The cases must use the user's local real questions and circuit images where
available. Each case needs an input identifier, expected capability, expected
material/image count, expected answer invariants, and a browser evidence link
or screenshot path. Unknown or unreviewed cases cannot be used as release
evidence.

## Current evidence before Release A completion

- A2 cold matrix: 10 rounds, 30/30 tasks completed, no result missing.
- A2 unique fingerprint count: 1.
- A2 legacy execution and drift counters: 0.
- A3/A4/A5/A6: not run or not complete.
- Release B Circuit capability: not started; Circuit stays out of this soak.

The final eight-hour run must start from the clean Release B stable baseline,
not from this dirty checkpoint. Any shared-layer fix during the final soak
resets the required soak window after the fix and requires the affected Golden
Set plus browser regression before continuing.
