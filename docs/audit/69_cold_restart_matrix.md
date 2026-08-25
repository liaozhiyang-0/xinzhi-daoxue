# Release A2 Cold Restart Matrix

Date: 2026-08-26
Checkpoint: `c0e68cf847aa4ccdc38299822932646210f6ee6e-dirty`
Harness: `scripts/release_a_cold_matrix.ps1`

This report supersedes the pre-capability-binding run recorded earlier in
this file. The service was restarted after the academic-writing binding was
registered, so the fingerprint below is the current Release A candidate
identity.

## Result

| Metric | Result |
|---|---:|
| stop/start rounds | 10/10 |
| tasks | 30 |
| completed | 30 |
| result missing | 0 |
| average round duration | 252.2 s |
| minimum round duration | 236.9 s |
| maximum round duration | 271.6 s |
| unique startup fingerprints | 1 |
| unique runtime generations | 1 |
| unique canonical plan versions | 1 |

All 30 tasks carried:

```text
runtime_generation = runtime-v3
canonical_plan_version = canonical-v1
startup_fingerprint = 4cf777dbb274a7f10a2cbcdd24aef9e3e9635d4d8b628016b121e5b29973dc1b
```

## Hard counters

The maximum observed value across all ten rounds was zero for:

```text
legacy_runtime_invocation_count
legacy_router_invocation_count
legacy_handler_invocation_count
legacy_plan_creation_count
legacy_checkpoint_execution_count
registry_drift_count
startup_fingerprint_mismatch_count
execution_target_not_active_count
shadow_result_mutation_count
```

Each round also reported database, Redis, MinIO, and configuration health as
ready before task submission. The circuit path was off for this Release A
matrix and recorded `circuit_decision_total_skip=3` per round; no Circuit
implementation was exercised here.

## Harness and launcher finding

The first restart attempt exposed a race in the Windows process ownership
scanner: a listener PID could disappear between `netstat` and the process
snapshot. The launcher was changed to ignore a missing snapshot entry rather
than issue a second unbounded process query. The focused launcher suite then
passed 28 tests, and the ten-round matrix completed without a stop timeout.

This is a shared launcher-boundary fix, not a task-specific patch. No database,
Redis, MinIO, or Qdrant data was deleted; the matrix only stopped and restarted
the services while retaining their data volumes.

## Evidence

Raw JSONL evidence is in the local runtime artifact:

```text
.codex-tmp/release-a-cold-matrix.jsonl
```

This report is an A2 pass for the current dirty Release A candidate. It is
not a Release A certification: A3 persisted state, A4 soak, A5 browser
matrix, and A6 final regression remain outstanding. The raw JSONL contains
the authoritative per-round evidence.
