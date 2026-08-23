# 产品分析指标字典 v1

Analytics 是现有业务表和结构化运行事件上的 bounded read model，不产生第二套业务真相。所有窗口均为 `window_start <= created_at <= window_end`，默认最多读取 `20,000` 行；超限返回 `truncated=true` 和数据质量警告。

## 账号与活跃

| 指标 | 定义 | 分母/边界 |
|---|---|---|
| `registered_users` | 当前账号表总数 | 不受窗口影响，仅 overview/users 返回 |
| `new_users` | 窗口内创建的账号数 | `accounts.created_at` |
| `active_users` | 窗口内创建 Session、发送 Message 或创建 Task 的去重用户数 | 去重 `user_id`，不展示给 Dashboard 的原始身份字段 |
| `active_users_daily/weekly/monthly` | 窗口结束时点向前 1/7/30 天有有效行为的去重用户数 | 以请求 `timezone` 计算；非法时区回退 UTC 并告警 |
| `returning_users` | 窗口内至少两个本地日期有行为的用户数 | 行为来自 Session、Message、Task |

## 会话与任务

| 指标 | 定义 | 分母/边界 |
|---|---|---|
| `sessions_created` | 窗口内创建的会话数 | `sessions.created_at` |
| `messages_per_session` | 消息数 / 会话数 | 会话数为 0 时返回 `null` |
| `followup_rate` | 同一会话中超过一次用户问题的会话 / 有用户问题的会话 | 只计 role=user |
| `tasks_created` | 窗口内创建的任务数 | `tasks.created_at` |
| `completion_rate` | completed / terminal tasks | terminal = completed + failed + cancelled |
| `failure_rate` | failed / terminal tasks | terminal 为 0 时返回 `null` |
| `cancellation_rate` | cancelled / terminal tasks | terminal 为 0 时返回 `null` |
| `retry_rate` | `attempt > 1` 的任务 / 任务数 | 仅在任务数大于 0 时计算 |
| `human_review_rate` | 需要人工复核的任务 / 任务数 | 来源为结果标记或反馈记录 |

## 回答与反馈

| 指标 | 定义 | 分母/边界 |
|---|---|---|
| `questions` | role=user 的消息数 | 当前筛选窗口和任务集合 |
| `evidence_coverage` | 有 evidence_view 的完成任务 / 完成任务 | completed 为 0 时 `null` |
| `citation_coverage` | 有 citations 的完成任务 / 完成任务 | completed 为 0 时 `null` |
| `feedback_coverage` | 有反馈的完成任务 / 完成任务 | completed 为 0 时 `null` |
| `resolved_rate` | resolved=true / 有 resolved 值的反馈 | 缺失 resolved 不进分母 |
| `satisfaction_rate` | satisfied / 有 satisfaction 值的反馈 | 缺失满意度不进分母 |
| `insufficient_evidence_count` | 结果明确标记 evidence_status=insufficient/empty 的完成任务数 | 不推断未声明的证据不足 |

## Agentic、RAG、工具与性能

| 指标 | 定义 |
|---|---|
| `planner_plan_count` / `planner_task_count` | 有 plan_id 的运行数 / 去重计划任务数 |
| `capability_usage` / `capability_task_count` | Agent capability 事件数 / 带 capability 的去重任务数 |
| `skill_usage` | `skill.selected` 结构化事件数 |
| `tool_usage` | Tool 节点数；没有节点时退回 tool 事件和 run.tool_calls |
| `tool_success_rate` | 成功 Tool 节点 / 成功+失败 Tool 节点 |
| `rag_usage` | retrieval_calls 与结构化检索事件之和 |
| `rag_empty_rate` | 空检索事件 / 检索调用 |
| `verification_usage` / `reflection_usage` | 验证节点/事件、反思/critic/revision 节点/事件计数 |
| `replan_rate` | bounded replan 任务 / planned tasks |
| `fallback_rate` | fallback 任务 / 任务数 |
| `task_latency_p50/p95/p99` | 终态任务从 created 到 completed/terminal 的分位毫秒数 |
| `queue_latency_p50/p95/p99` | created 到 started 的分位毫秒数 |
| `<stage>_latency_p50/p95/p99` | planner、retrieval、tool、provider、verification、presentation 阶段的 run metrics 分位数 |
| `runtime_retry_rate` | `attempt > 1` 的任务 / 任务数 |

## 公共筛选

API 支持 `from`、`to`、`timezone`、`course`、`role`、`intent`、`capability`、`skill`、`tool`、`scenario`、`provider`、`model`、`pilot_batch`、`task_id`、`row_limit`。`task_id` 查询只保留该任务所属会话和消息，避免单任务排查混入其它会话。

