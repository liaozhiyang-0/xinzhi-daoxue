# Analytics source-of-truth map (A0)

Analytics must be a read model over existing operational data. No new product truth is introduced here.

| Product concept | Existing source | Safe dimensions |
|---|---|---|
| Account | `accounts`, `auth_sessions` | role, status, created/login dates |
| Session | `sessions`, `conversation_messages`, `session_summaries`, `memories` | user, course, activity dates, archived state |
| Task | `tasks`, `task_events` | status, course, intent, provider, agent, timestamps, attempt |
| Answer quality | `task_feedback`, terminal `tasks.result_content` | resolved, satisfaction, review, evidence/citation metadata |
| Agentic execution | `agent_runs`, `agent_run_nodes`, `agent_plan_proposals`, structured task events | run kind, provider, node type, status, latency, retry/replan |
| Attachments | `files`, task attachment references | content type, ingestion status, size, task/user |
| Audit | `audit_logs` | actor role, action, target, timestamp |

Dashboard queries must use bounded time windows and aggregation. Raw prompts, private attachment text, credentials, and student identifiers are not dashboard fields.
