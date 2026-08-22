# Phase D1：Existing Verification Audit & Reflection Contract

## Existing ownership audit

| Existing capability | Evidence | Phase D treatment |
| --- | --- | --- |
| Academic Solver deterministic/domain checks | `high_risk_verification.py`, `solver_quality_gate.py`, `academic_solver_graph.py` | KEEP as deterministic verifier; Critic cannot override it |
| Runtime observe/decide/act/verify/replan | Runtime services and `RuntimeExecutionBoundary` | KEEP shared Runtime Kernel and bounded replan; no second controller |
| Result validation and terminal usability | `agent_result_governance.py`, `RuntimeResultPipeline`, `TaskRuntimeExecutionService` | KEEP as publish boundary; Reflection runs before commit and cannot publish |
| Knowledge evidence/citation validation | `AgentResultValidatorRegistry._learn`, retrieval/evidence packet services | KEEP evidence and citation gate; Critic only identifies review candidates |
| Research provenance/review | `external_research_runtime.py`, `research_analysis_review.py`, `research_analysis_planner.py` | KEEP provenance/review; reuse as Critic evidence input |
| Teaching verification/review | `TeachingFoundationService`, `StudentVerificationService`, assignment/lesson runtimes | KEEP pedagogical and factual checks; Teaching Critic is risk-triggered |
| Internal model workers | `InternalAgentHub` and `InternalAgentExecutionService` | REUSE as the only Critic/Revision worker host; no public Agent ID |
| Solver patches | `HighRiskVerificationService` and `SolutionPatch` | KEEP deterministic local patch path; Reflection revision is separate and bounded |

## Contract ownership

```text
Draft AgentResult
       │
       ├── existing deterministic/domain verification
       │       └── SolverQualityGate / evidence / governance
       │
       └── ReflectionPolicy → CriticResult → optional RevisionProposal
                                  │                 │
                                  └── trace only    └── one change → existing reverify
```

`CriticResult` is advisory. It cannot set a terminal state, change tool output,
change citation IDs, invent evidence, or bypass `RuntimeResultPipeline`.
`RevisionProposal` is applied only to answer/business fields outside the immutable
evidence/tool/verification keys, and the resulting draft is revalidated before commit.

## Unified contracts

`apps/api/app/contracts/reflection.py` defines:

- `CriticResult`: `pass | revise | fail | needs_review`, issue taxonomy, severity,
  issue summary, grounded evidence refs, unsupported claims, required changes,
  confidence, version, and revision permission;
- `ReflectionDecision`: `skip | critique | needs_review | fail`, reason codes,
  critic budget, required verifiers, and `max_revision_count <= 1`;
- `RevisionRequest` / `RevisionProposal`: original draft, bounded allowed changes,
  evidence refs, revision count/budget, and revision diff summary;
- `ReflectionTrace` / `ReflectionMetrics`: mode, decision, critic/revision result,
  latency/tokens, unsupported critique count, disagreement, and final status.

## Tests

`apps/api/tests/test_reflection_framework.py` covers:

- default-off and low-risk skip;
- Academic Solver, Knowledge, and Research trigger decisions;
- critic shadow observability with unchanged answer;
- unsupported evidence refs converted to `needs_review`;
- critic failure isolation;
- one bounded revision with re-verification and immutable tool observations.

## D1 conclusion

`D1 = PASS`. Existing verification remains authoritative and the new Reflection contract
is a single internal advisory boundary rather than a replacement verifier or Runtime.
