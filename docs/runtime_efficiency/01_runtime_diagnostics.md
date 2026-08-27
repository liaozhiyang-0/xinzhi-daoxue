# Runtime diagnostics contract

统一诊断载荷为 `runtime_timing.v1`，挂在任务结构化结果中，使用现有 Runtime，不新增 Runtime、LangGraph 或第二套编排器。每个 trace 包含：

- `events`：请求接收、阶段开始/结束、模型调用、工具节点和完成事件；保存时间、耗时、状态和有限元数据。
- `stages`：`request_preparation`、`routing`、`runtime_execute`、`planner`、`context_build`、`rag`、`model`、`tool`、`reflection`、`quality_gate`、`result_validation`、`task_commit` 等阶段的耗时与 `outcome`。
- `counters`：模型、工具、RAG、重试、fallback 和质量门计数。
- `context_usage`：上下文字符/消息/文档数量与哈希；不保存原始 prompt、answer 或 token 内容。
- `fingerprints`：有限数量的上下文、结构化结果和事件指纹，用来比较重复运行，不用来还原用户内容。

本轮最小实现补齐了失败状态和尾部阶段：`timed_stage` 在异常时记录 `outcome=failed` 后继续抛出；模型调用使用其状态；工具节点同时记录 `tool` 与 `tool_execution`；结果校验和任务提交分别可观测。SSE 仍由稳定性脚本记录首事件、首个可用内容和终态，且明确标注为可用内容事件，不冒充 token-level TTFT。

相关实现：`apps/api/app/observability/runtime_timing.py`、`apps/api/app/services/task_runtime_execution.py`、`apps/api/app/services/task_completion.py`、`scripts/run_runtime_stability.py`。
