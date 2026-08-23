# Architecture Overview

The current production control chain is:

```text
User Input
  -> API / non-blocking Task creation
  -> Unified ingress / GoalContract
  -> deterministic preflight
  -> Planner + Capability/Skill binding
  -> CanonicalPlan
  -> Task Runtime preparation
  -> Runtime Plan / checkpoint / recovery
  -> Agent execution
  -> RAG / Tool / Model provider
  -> verification / reflection gate
  -> result presentation and commit
```

The architecture audit remains the source of truth for ownership and consolidation. Phase N does not add a second Runtime, second trace system, or another public Agent. Planner, Skill, Reflection, Experience and Evaluation remain bounded capabilities behind the existing task/runtime contracts. Overall Router, IntentPlanCompiler and legacy-runtime remain compatibility-only boundaries during persisted-checkpoint migration.

## Compatibility surface

The following interfaces remain the release boundary:

- Task API and non-blocking `202` creation semantics;
- `AgentRequest`, `AgentResult`, `RuntimePlan` and checkpoint snapshots;
- RAG retrieval/context/citation contracts;
- Tool registry and declared capability contracts;
- SSE event order, reconnect and terminal-state semantics;
- OpenAPI and generated frontend TypeScript contract.

## Operational invariant

Unknown, unavailable, unverified or failed evidence must remain observable as warning, degraded, review, failed or suspended state. The RC does not convert those states into fabricated success.
