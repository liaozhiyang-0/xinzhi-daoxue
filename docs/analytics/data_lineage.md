# Analytics 数据血缘

```text
Account / AuthSession ─┐
Session ───────────────┼─> AnalyticsService._load (bounded window)
Message ───────────────┤
Task / TaskEvent ──────┤
Feedback ──────────────┤
AgentRun / RunNode ────┤
PlanProposal ──────────┘
                         ↓
                dimension filters
                         ↓
                bounded aggregation
                         ↓
        /api/v1/analytics/{kind} read model
                         ↓
             Admin / Teacher dashboard
```

## 字段来源

| 领域 | 数据源 | 使用字段 |
|---|---|---|
| 身份 | `accounts` | id、role、created_at |
| 会话 | `sessions` | id、user_id、course_id、created_at、last_message_at |
| 问题 | `conversation_messages` | session_id、user_id、role、created_at |
| 任务 | `tasks` | status、course_id、intent、provider、agent_id、attempt、timestamps、脱敏维度元数据 |
| 运行 | `agent_runs`、`agent_run_nodes` | plan、node、status、latency、retrieval/tool 计数 |
| 计划 | `agent_plan_proposals` | bounded replan 任务关联 |
| 事件 | `task_events` | plan、route、retrieval、verification、reflection、resume 等结构化事件 |
| 反馈 | `task_feedback` | resolved、satisfaction、problem_type、manual_review_required |

## 安全与性能边界

- `_load` 对任务、会话、消息、反馈、运行和事件使用窗口、倒序和 `row_limit + 1`，只用额外一行判断截断。
- 对用户角色的过滤先取相关账号角色，再在内存中筛选；不把 login、学号或原始输入放进响应。
- 原始 `input_content` 只用于服务内部读取已约定的维度键，不直接返回；任务 ID 筛选只展开对应会话。
- Analytics 不解析日志文本，不写业务表，不调用 Provider，不改变 Task Runtime。

