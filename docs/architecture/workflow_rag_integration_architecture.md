# 工作流与 RAG 融合架构

## 目标与边界

任务链只执行一次检索，并把同一 `WorkflowContextBundle` 交给输入映射、Provider、引用校验和展示层。现有 `POST /api/v1/tasks`、Provider、知识库、索引及已发布 LEARN_01 / SOLVER_CT Flow 均保持不变。

```text
AgentRequest
  -> RouteDecision / AgentExecutionPlan
  -> RAGRetrievalService（至多一次）
  -> RetrievalContextPacket
  -> WorkflowContextBundle
     -> retrieved_context（仅 grounded_generation 注入云端）
     -> CitationValidator
     -> TaskExecutionSummary
     -> presentation + evidence_view
```

## WorkflowContextBundle

定义位于 `app/contracts/runtime.py`，包含 request/task/agent/course/intent、检索策略、RAG 交互模式、RAG 与证据状态、格式化上下文、最终证据、相关图片、进入工作流和实际引用的证据编号、警告、索引版本与 Trace ID。

`RetrievalContextPacket` 仍是检索格式化输入；Bundle 是跨执行链的统一视图。TaskRunner 在检索后只构建一次 Packet/Bundle。云端失败时，本地 fallback 复用同一个 `RetrievalResult`，不再次调用 RAG。

## RAG 交互语义

| 语义 | 输入边界 | 展示边界 |
|---|---|---|
| `grounded_generation` | 证据进入工作流 | 仅 CitationValidator 认可的 S 编号标为已引用 |
| `reference_only` | 不声明为生成依据 | 补充阅读 |
| `method_reference` | 不改写题目事实，不进入冻结 SOLVER Flow | 独立“方法参考” |
| `user_sources_only` | 只允许用户提供来源 | 不用课程库支撑科研结论 |
| `data_context_only` | 只允许结构化业务数据 | 标明数据上下文 |
| `no_rag` | 不检索 | 不展示证据 |

现有配置映射：LEARN_01 为 `grounded_generation`；SOLVER_CT 为 `method_reference`；`external_source_context` 映射为 `user_sources_only`；教学数据分析映射为 `data_context_only`。

## 兼容与安全

- 旧结果字段保留，新字段放在 `structured_result.presentation`、`execution_summary`、`evidence_view` 和 `workflow_context`。
- 学生端只消费 presentation、summary 与 evidence_view。
- `/api/v1/debug/execution/{task_id}` 从已持久化任务和事件构建统一调试视图，并递归脱敏敏感键。
- SOLVER_CT 的检索证据不会进入 `workflow_evidence_ids`，也不会被展示为云端答案依据。
