# Reflection Phase D Closeout

## Final control flow

```text
User Goal / CanonicalPlan
          ↓
Existing Skill / Tool / RAG / Worker / Academic Solver
          ↓
Draft AgentResult
          ↓
Existing deterministic/domain verification
          ├── unusable/fail → existing fail-closed Result Pipeline
          └── usable
                 ↓
          ReflectionPolicy
          ├── skip → existing publish gate
          └── critique → Internal Critic Worker
                              ├── pass → existing publish gate
                              ├── fail/review → existing review/fail-closed path
                              └── revise → one bounded Revision
                                              ↓
                                      existing re-verification
                                              ↓
                                      Governance / Publish
```

## KEEP / MERGE / FREEZE / REMOVE

| Treatment | Component | Phase D conclusion |
| --- | --- | --- |
| KEEP | Runtime Kernel, task lifecycle, checkpoint/recovery | Reflection uses the existing boundaries |
| KEEP | SolverQualityGate, domain/tool verification, evidence/citation gates | These remain authoritative |
| KEEP | Result Governance and Task completion boundary | Critic cannot publish or set terminal state |
| KEEP | InternalAgentHub | Hosts Critic/Revision as internal workers only |
| MERGE | Existing verification signals + ReflectionPolicy inputs | One trigger decision, no duplicate verifier |
| MERGE | Critic trace + evaluation metrics | One auditable `reflection.v1` trace |
| FREEZE | Public Agent IDs, Academic Solver decomposition, Planner/Skill takeover | No expansion in Phase D |
| FREEZE | Experience Memory, automatic promotion, automatic canary expansion | Reserved for Phase E or later |
| REMOVE | Critic as public Agent, second Runtime, second checkpoint, recursive Critic loop | Forbidden by contract and tests |

## Phase D invariants

- `ReflectionPolicy` is risk-triggered; default switches are OFF.
- Critic is an Internal Worker and cannot directly publish a result.
- Critic may reference only existing evidence/tool refs; unsupported refs become `needs_review`.
- Revision is bounded to one attempt and cannot alter immutable evidence/tool/verification data.
- Revision re-enters the existing deterministic/domain and result validation gates.
- Critic failure is isolated; existing fail-closed behavior is preserved.
- Academic Solver, Knowledge, Research, and risk-triggered Teaching are covered.
- Evaluation evidence distinguishes synthetic from real Provider evidence.
- Canary is default OFF, allowlisted, rollback-capable, and never auto-expands.
- No Experience Memory, automatic self-improvement, new public Agent, second Runtime, or
  second checkpoint was implemented.

## Evidence and next insertion point

The provider-free D6 report is `CONDITIONAL_GO`. A future real/offline case run may populate
`ReflectionEvaluationObservation` from actual traces; only then can a real `GO` be considered.
Phase E may later consume the final ReflectionTrace as an input, but Phase D does not persist
it as Experience Memory or promote a strategy automatically.

## D7 conclusion

Phase D implementation and Phase D-scoped local verification are complete. The full test
run in the pre-existing dirty worktree reported `1921 passed, 15 skipped, 6 failed`; the
failures are in unrelated commercial-scenario, embedding, external-source, Task API, and
unified-web-UI changes, and no Phase D-scoped test failed. Commit/push/CI verification is
performed once for the entire Phase D release, after unrelated working-tree changes are
excluded from staging.
