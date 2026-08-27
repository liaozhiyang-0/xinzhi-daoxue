# C2：SVG Artifact 集成

SVG 不进入 answer_text。

正确结构：
CircuitRenderResult
├── compact observation → Runtime
└── SVG → Artifact Store

优先复用现有 MinIO / Artifact infrastructure，类型：
`image/svg+xml`

Runtime 只保留：
artifact_ref、renderer、validation_state、warnings、render_latency_ms

禁止把大段 SVG 写入：
prompt、answer_text、session summary、memory。

前端展示：
Answer + Circuit Diagram Card

要求：
可展开、刷新后恢复、历史会话恢复。

SVG 按不可信内容处理；如内联必须经过现有 sanitize 边界，优先安全 artifact rendering。

Artifact storage fail 不得影响 Solver 正文。

浏览器验收：
10 次画图
5 次刷新恢复
3 次历史恢复

提交：
`feat(circuit): persist rendered circuits as artifacts`

输出：
`docs/audit/52_circuit_artifact_report.md`
