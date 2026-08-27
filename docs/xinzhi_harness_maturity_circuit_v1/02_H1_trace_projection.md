# H1：Unified Trace / Span Projection

目标：借鉴主流 Agent Harness 的 Trace/Span，但不改变 Runtime 执行。

基于现有：
TaskEvent、AgentRun、Runtime Node、Checkpoint、Provider metrics、Tool events

增加只读：
`TraceProjectionService`

投影结构：
trace
├── ingress
├── planning
├── retrieval
├── model
├── tool
├── verification
└── presentation

Span 最小字段：
trace_id、span_id、parent_span_id、span_type、name、status、start_time、end_time、duration_ms、provider、tool_id、error_code、input_summary、output_summary。

敏感输入脱敏。

禁止：
- 新 event bus
- 改 TaskEvent schema
- 改 checkpoint
- Trace 成为 Runtime 依赖

优先增强现有 `/api/v1/debug/traces/{trace_id}`，不要新建平行接口。

验收：
关闭 Trace 时任务行为完全一致；开启后可看到 planner/model/RAG/tool/verify latency。

回归：
Target tests + 六场景 smoke + 浏览器文字题 + 图片题。

提交：
`feat(obs): add runtime trace projection`

输出：
`docs/audit/47_trace_projection_report.md`
