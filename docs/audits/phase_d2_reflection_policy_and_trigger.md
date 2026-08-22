# Phase D2：ReflectionPolicy & Trigger Strategy

## Policy

`ReflectionPolicy` is provider-free and does not select Agents, Skills, or Tools.
It maps the already selected workflow to one of four actions:

```text
skip | critique | needs_review | fail
```

Inputs include capability, result risk/complexity, evidence status, deterministic
quality status, fallback/degraded state, manual-review flags, and the remaining
time budget.

## Trigger matrix

| Situation | Decision | Reason |
| --- | --- | --- |
| Reflection switches disabled | `skip` | `reflection_disabled` |
| Capability outside Academic/Knowledge/Research/Teaching | `skip` | `capability_not_supported` |
| Agent not in explicit allowlist | `skip` | `agent_not_allowlisted` |
| Fallback/degraded result | `skip` | `degraded_fallback` |
| Budget exhausted | `needs_review` | `reflection_budget_exhausted` |
| Existing result is unusable/failed | `fail` | `deterministic_result_unusable` |
| Complex/high-risk Academic Solver | `critique` | `high_risk_solver` |
| Knowledge evidence insufficient or synthesis needs review | `critique` | `evidence_quality_warning` / `knowledge_synthesis_candidate` |
| Research unsupported claim/conflict | `critique` | `research_evidence_conflict` |
| Teaching manual-review candidate | `critique` | `teaching_review_candidate` |
| Simple low-risk result with no warnings | `skip` | `low_risk_no_trigger` |

Shadow and bounded revision are both disabled by default in `Settings`. The configured
canary allowlist can narrow the scope further. The policy enforces a hard maximum of one
revision and never recursively invokes Critic.

## D2 conclusion

`D2 = PASS`. Low-risk tasks do not incur a Critic call; risky/uncertain tasks can be
observed by Critic when the explicit Reflection switch and allowlist permit it.
