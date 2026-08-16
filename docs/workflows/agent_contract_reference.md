# Agent 契约参考

## AgentDefinition

必需区块为身份/版本、`provider`、`capabilities`、`input_contract`、`input_mapping`、`output_mapping`、`retrieval_policy` 和 `fallback`。旧式字符串 `provider`、扁平 input/output mapping、`knowledge_top_k` 与 `knowledge_context_mode` 仍可加载，但会在 schema v2 后续主版本移除。

Provider Parser：`json`、`fixed_line_fields`、`plain_text`、`json_or_fixed_line`、`custom_registered_parser`。

输入 Transform：`string`、`json_string`、`bool_string`、`number_string`、`truncate`、`default`、`join_lines`、`retrieval_context`。禁止 `eval` 和任意表达式。

检索模式：`no_rag`、`text_rag`、`multimodal_rag`、`method_only_rag`、`data_context_only`、`external_source_context`。Reranker 为 `off/on/conditional`。

Fallback handler：`local_retrieval_answer`、`static_template`、`planned_response`、`manual_review`、`no_fallback`。失败原因必须匹配 `trigger_on`；不允许全部 Agent 统一降级到 LEARN。

## 请求与结果

`TaskRequestContext` 包含 task/request/session/user、原始与标准化问题、课程、意图、输入模态、安全附件引用、会话摘要和 options。正式 API 新字段保持可选。

结果业务字段放入 `business_data`。顶层统一信息包括 status、Agent/Provider、课程/意图、answer、confidence、citations/images/warnings、RAG/evidence/cloud/fallback 状态、timings、schema version。未知字段向前兼容；原始响应只允许受控 Trace 保存脱敏摘要。

## 运行时规则

- enabled 的本地 Agent 必须声明可用 handler；handler 缺失时 `local_ready=false`。
- planned Agent 可在 Debug 展示和 dry-run，但正式 Router 不选中。
- `route_when_unconfigured` 仅用于兼容冻结基线：可选中后在 TaskRunner 提前失败，不会绕过本地 Runtime。
- 图片二进制不进入通用字符串 Context；SOLVER 的单图仍走现有安全上传字段。
- Provider 业务 failed 和解析错误不重试；本地 Runtime 重试由计划预算和 deadline 共同限制。
