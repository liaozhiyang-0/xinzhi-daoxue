# Phase D5：Verification & Publish Gate Integration

## Authoritative order

```text
Generate
  ↓
Existing deterministic/domain verification
  ├── fail → existing fail-closed Result Pipeline
  └── pass/usable
          └── ReflectionPolicy → Critic
                    ├── pass → existing publish gate
                    └── revise → one Revision → existing reverify → publish gate
```

Critic `pass` cannot clear a deterministic failure, citation/evidence failure,
permission/side-effect failure, or unusable result. Result publication still requires
`AgentResultValidatorRegistry` and the existing `TaskRuntimeExecutionService` terminal
boundary. Reflection only adds `structured_result["reflection"]` trace metadata unless a
fully verified bounded revision succeeds.

## Issue taxonomy mapping

The existing domain issue types remain authoritative (`equation`, `calculation`, `unit`,
`direction`, `condition`, `logic`, `evidence`, `citation`, `tool_conflict`). Reflection
uses the compatible higher-level labels `reasoning`, `numerical`, `unit`, `factual`,
`missing_evidence`, `citation`, `scope`, `format`, `safety`, `tool_conflict`,
`unsupported_claim`, and `incomplete_solution` as advisory issue types.

## Capability ownership

- Academic Solver: domain verification and `SolverQualityGateService` first;
- Knowledge: evidence and citation validation first;
- Research: provenance and unsupported-claim review first;
- Teaching: pedagogical Critic is advisory; factual/domain checks remain deterministic.

## D5 conclusion

`D5 = PASS`. Reflection is downstream of the draft and upstream of the same publish gate;
it cannot become a second acceptance authority.
