# Current metric inventory (A0)

## Already available

- Admin account/session/audit summaries from `/api/v1/admin/*`.
- Admin task and file summaries from `/api/v1/admin/*`.
- Teacher learning metrics from `/api/v1/learning/metrics`.
- Feedback metrics from `/api/v1/feedback/metrics`.
- Runtime and execution trace metadata from `/api/v1/debug/execution/*` and task events.
- Agent registry/readiness metadata from `/api/v1/agents/*` and scenario preflight.

## Unified product metrics delivered

- bounded overview with one shared filter contract;
- DAU/WAU/MAU and role distribution;
- session activity, messages/session, follow-up rate;
- task terminal denominators and completion/failure/cancellation rates;
- evidence/citation/feedback coverage;
- planner/capability/skill/tool/RAG/verification/reflection/replan/fallback usage;
- p50/p95/p99 latency for task, queue, run and populated runtime stages;
- six-case, scenario, task and pilot batch filters.

These metrics are exposed through `/api/v1/analytics/{overview,users,sessions,tasks,answers,agentic,performance,courses}` and `/api/v1/analytics/teacher`. They are aggregation APIs over the sources above, not log-text parsing.
