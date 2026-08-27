# C3：AUTO Render + Plan Pattern

仅在 C1/C2 稳定后执行。

先保持：
CIRCUIT_RENDER_ENABLED=true
CIRCUIT_RENDER_AUTO=false

增加可选 `plan_pattern` metadata，不重做 CanonicalPlan。

建议值：
DIRECT
RETRIEVE_THEN_ANSWER
SOLVE_THEN_VERIFY
SOLVE_VERIFY_RENDER
PARALLEL_RETRIEVE_SYNTHESIZE

AUTO 适合：
- 等效电路
- 戴维宁
- 诺顿
- 小信号
- 运放反馈结构
- 复杂多节点拓扑
- 用户要求重画

通常不 AUTO：
- 单纯数值计算
- 定义解释
- 判断题
- 简单公式

不要让 LLM 随机自由决定。
推荐：deterministic trigger + planner hint + CapabilitySpec。

AUTO 仍是 optional branch：
SOLVE → VERIFY → optional RENDER

Renderer 永远不是 Solver terminal gate。

浏览器至少：
10 个应触发 AUTO
10 个不应触发 AUTO

记录 false positive / false negative / latency。

提交：
`feat(circuit): add conservative automatic render policy`

输出：
`docs/audit/53_circuit_auto_policy_report.md`
