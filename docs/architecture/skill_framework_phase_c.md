# Phase C Skill Framework Architecture

Phase C keeps Planner and Runtime ownership stable while adding one bounded Skill control plane.

```text
User Goal → Supervisor → TaskRouter → PlannerService
                                      ↓
                         SkillRetriever / SkillPolicy
                                      ↓
                         authoritative SkillRegistry
                                      ↓
                         CanonicalPlan + trace metadata
                                      ↓
                         SkillBindingService / adapter
                                      ↓
                         existing Runtime Kernel
                         ↙       ↓        ↘
                    Tool    Worker      RAG/Academic Solver
                                      ↓
                         Verification → Result Commit
```

Skills are registered, retrievable, policy-checked, and bound to existing handlers. They do not
own a Task lifecycle, Provider call, checkpoint store, or public Agent identity. Planner takeover
and the controlled canary remain default-off and allowlist-gated. Reflection, SkillMemory, and
automatic canary expansion are explicitly outside Phase C.

Compatibility remains at Task/Chat API, AgentRequest/AgentResult, CanonicalPlan/Runtime Plan,
Checkpoint/Recovery, RAG, Tool, and event/SSE boundaries. `OverallRoutingService` remains only
as an explicit legacy compatibility wrapper.
