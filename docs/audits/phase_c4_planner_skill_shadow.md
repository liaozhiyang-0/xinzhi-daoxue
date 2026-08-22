# Phase C4 Planner Skill Shadow Integration

## 控制流

```text
existing RouteDecision / IntentExecutionPlan
              |
              v
       PlannerService (shadow)
              |
              +--> SkillRetriever (bounded deterministic top-k)
              |
              +--> SkillPolicy (registered/version/prereq/dependency/evidence/risk)
              |
              v
CanonicalPlan.selected_skills + planner_skill_selection + rejection reasons
              |
              v
TRACE / plan.created event / evaluation snapshot only
```

The Planner is configured with the composition-root `SkillRegistry`; no second
registry is created. Skill candidates are not Runtime nodes, are not executed,
and do not create Agents or canary traffic. `CanonicalPlan.nodes` remains the
existing plan shape, while skill choice is recorded as bounded metadata.

## Shadow fields

- `CanonicalPlan.selected_skills`: only policy-approved registered IDs;
- `CanonicalPlan.skill_selection`: score, version, match reasons and rejection
  status for trace/evaluation;
- `PlannerSnapshot.current_skills`: old `RouteDecision`/Intent plan selection;
- `PlannerSnapshot.planner_skills`: bounded Retriever/Policy selection;
- `PlannerSnapshot.skill_selection_status`: `selected`, `empty`, `rejected` or
  `unavailable`;
- `PlannerSnapshot.skill_rejection_reasons`: stable fail-closed reasons.

When the registry is unavailable, the snapshot records
`skill_registry_unavailable` and preserves the old route. For a general or
unsupported course, the selection is empty; course alone never selects all
course skills. An explicit takeover flag is not changed by C4.

## Five shadow cases

| Case | Expected skill observation |
|---|---|
| Academic CT / node voltage | `CT.NODAL` selected after `CT.KCL` prerequisite |
| Knowledge QA | `KNOWLEDGE.QUERY_REWRITE` selected; grounded explanation remains gated |
| Teaching CT / first order | `CT.FIRST_ORDER_INITIAL` selected after KCL/KVL |
| Research query planning | `RESEARCH.QUERY_PLANNING` selected with worker/evidence state |
| General fallback | empty selection; no course pollution |

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q --no-cov `
  apps/api/tests/test_planner_skill_shadow.py `
  apps/api/tests/test_planner_contract.py `
  apps/api/tests/test_planner_shadow_mode.py
```

The canary/takeover flag remains unchanged and C4 does not introduce Critic,
Reflection, SkillMemory or Runtime skill execution.
