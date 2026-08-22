# Planner Phase B Final Architecture

## Final control flow

```text
User Input
  ↓
FastAPI /tasks or /chat
  ↓
Supervisor
  └─ API normalization / legacy compatibility / trace envelope
  ↓
TaskRouter
  └─ deterministic route + AgentRegistry/InternalAgentHub preflight
  ↓
PlannerService
  ├─ GoalInterpreter
  ├─ CandidateBuilder
  ├─ PlannerPlanCompiler
  └─ PlannerSnapshot + lineage + shadow/takeover policy
  ↓
CanonicalPlan
  └─ adapter to IntentExecutionPlan / AgentRunPlan / RuntimeGoal
  ↓
Runtime preparation
  ├─ context assembly only once on the active path
  ├─ checkpoint restore uses the saved request/plan
  └─ no Overall Router refinement on Planner takeover
  ↓
Runtime Kernel
  └─ Agent / Tool / RAG / Provider execution
  ↓
Verification / Result Governance / Result Commit
```

`OverallRoutingService` no longer participates by default. It remains a deprecated
compatibility wrapper only when `OVERALL_ROUTING_ENABLED=true` is explicitly supplied
for rollback or an older deployment.

## Phase B ownership

| Layer | Owner after Phase B | Boundary |
| --- | --- | --- |
| API and legacy request shape | Supervisor | `AgentRequest`, `AgentResult`, Chat/Task API |
| deterministic preflight | TaskRouter + registries | Agent/capability availability and target validity |
| intelligent control snapshot | PlannerService | Goal, candidates, canonical plan, lineage |
| plan semantics | CanonicalPlan | versioned, provider-free plan vocabulary |
| execution and recovery | Runtime Kernel | Run, checkpoint, retry, resume, cancel |
| result acceptance | Verification/Governance | validation, disclosure, commit |
| legacy second-pass route | OverallRoutingService | deprecated, explicit opt-in only |

Planner Phase B is a structural ownership transition. The current implementation is
provider-free and deterministic; it does not claim real-model answer-quality parity.
Skill retrieval, reflection, and experience memory remain Phase C+ work.

## Compatibility guarantees

The following contracts remain stable and are adapted rather than removed:

- Task API and Chat API;
- `AgentRequest`, `IntentExecutionPlan`, `AgentExecutionPlan`, `AgentRunPlan`;
- `AgentResult` and result governance;
- Runtime Run, Checkpoint, Recovery, Retry, Cancel and Resume behavior;
- RAG and Tool interfaces;
- task event ordering and SSE replay/reconnect.

No public Agent ID was added. `ACADEMIC_PROBLEM_SOLVER` remains the academic solver
boundary; its internal execution complexity is not split into new public Agents.

## Phase C handoff only

Phase C may introduce `skills/`, `SkillRegistry`, `SkillRetriever`, and bounded
Skill/Reflection contracts against the canonical plan. This phase does not implement
those capabilities.
