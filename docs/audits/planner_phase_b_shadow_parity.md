# Phase B4 Planner Shadow Parity Report

- Evidence level: `synthetic_provider_free`
- Cases: `5`
- Readiness: **GO_FOR_CONTROLLED_CANARY**
- Production takeover performed: **No**

## Scope

This is a deterministic, provider-free structural evaluation. It validates the Planner adapter, TaskRouter preflight inputs, canonical plan shape, lineage, and failure-safety contracts. It is not a real-model quality or production traffic benchmark.

## Quantitative checks

| Check | Observed | Threshold |
| --- | ---: | ---: |
| invalid target rate | 0.000 | <= 0.000 |
| unsupported capability rate | 0.000 | <= 0.000 |
| critical route regression rate | 0.000 | <= 0.000 |
| Planner error rate | 0.000 | <= 0.010 |
| route parity rate | 1.000 | >= 0.990 |
| plan parity rate | 1.000 | >= 0.990 |
| max observed adapter latency (ms) | 0.000 | <= 100.000 |
| token/cost overhead | 0.000 | <= 0.000 |
| resume/rollback integrity | True | required |

## Disagreement taxonomy

- `old_route_wrong_planner_better`: 0
- `planner_wrong_old_route_better`: 0
- `both_valid`: 5
- `insufficient_evidence`: 0
- `availability_or_fallback_difference`: 0

## Decision

GO is limited to the provider-free, deterministic controlled-canary scope. It does not authorize default Planner takeover or establish real model answer-quality parity. The canary remains explicitly allowlisted and rollback-capable.

Reproduce with:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_planner_shadow.py
```
