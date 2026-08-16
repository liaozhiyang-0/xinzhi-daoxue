# 多工作流本地运行架构

## 目标与审计结论

统一调用链为：正式任务 API → `TaskRequestContext` → `TaskRouter` → `AgentExecutionPlan` → 现有 `RAGRetrievalService` → `AgentInputMapper` → Local Runtime / ModelService → `WorkflowOutputParserRegistry` → Citation/格式校验 → `AgentResult` 兼容响应 → Agent 级 fallback。

可直接复用的模块是 `AgentRegistry`、`TaskRouter`、`TaskRunner`、`RAGRetrievalService`、`RetrievalContextService`、`CitationValidator`、事件/Trace 和正式任务 API。原有专用逻辑包括 Router 对 `SOLVER_CT_V1` 的名称判断、TaskCreation 对 CHECK→SOLVER 的提示词判断、TaskRunner 对 `learning_qa` 的检索注入与 fallback 判断，以及 Provider 内部的 LEARN 行协议解析。

本次把这些判断分别迁移为 `route_when_unconfigured`、`fallback.instruction_prefix`、`retrieval_policy.generation_injection`、`fallback.handler` 和 Parser Registry。保留的旧字段只用于兼容加载，计划在 registry schema v2 稳定后、下一个主版本移除。

## 核心协议

- `AgentDefinition`：身份、版本、发布状态、Provider、能力、输入契约、输入/输出映射、检索策略和 fallback。
- `TaskRequestContext`：只标准化一次，保留原始 `canonical_input`，附件只保存安全引用。
- `AgentExecutionPlan`：确定性计划，记录 RAG、图片、Reranker、预算、deadline、配置状态和跳过阶段。
- `AgentResultEnvelope`：面向新 Agent 的统一结果；现有 `AgentResult` 以可选字段兼容同一信息。

启动加载注册表时会拒绝重复 YAML 键、未知 Parser/Transform/Retrieval/Fallback、无效输出目标、不可用 Runtime Agent，以及 required 输入缺少映射。配置不完整不会泄漏，只令 `configured=false`；TaskRunner 在执行前停止。

## Provider、解析与安全

真实模型 Provider 共用受控的 HTTP 客户端和并发/超时边界；本地 Agent 不创建第二套网络调用链。网络和 5xx 计入 Circuit Breaker，4xx、业务失败、解析错误不触发熔断。

`AgentInputMapper` 只支持有限 Transform，不执行表达式。日志和 Debug 只返回字段长度及120字符以内的脱敏预览。`WorkflowOutputParserRegistry` 支持 JSON、JSON 围栏/前后杂质、固定行、纯文本、JSON-or-fixed-line 和显式注册的 custom parser。

## RAG 与本地性能

RAG 服务保持唯一实例。BM25 与 Dense 通过有界线程池并行，图片检索只在计划启用时执行；文本、图片和 Reranker 各自有并发闸门。三类模型均为单例、懒加载，并使用首次加载锁。conditional Reranker 仅在总结任务、候选分差过小或通道冲突时加载。

缓存键包含标准化查询、课程、意图、策略名、索引版本、模型修订、图片和 Reranker 状态；结果缓存使用 TTL+LRU，索引版本改变即自然失效。

## Trace、Debug 与兼容边界

任务结果的 `structured_result.execution_plan` 保存脱敏计划；Debug 页增加 Agent 注册、Provider 状态、映射预览和 dry-run。`POST /api/v1/tasks`、已有 SSE 事件顺序和 RAG Debug API 保持稳定。原始模型响应、API Key、Secret、Authorization、绝对知识库路径和向量均不向前端返回。
