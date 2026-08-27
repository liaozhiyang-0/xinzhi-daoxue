# R：最终回归与 Release Gate

必须重新跑：

主线：
- 六业务场景
- 普通文本
- 单图
- 多图
- 长对话
- provider timeout
- retry/cancel
- SSE
- history restore

Harness：
- Trace Projection optional
- Semantic Eval optional
- CapabilitySpec backward compatible
- Tool Guard optional

Circuit：
OFF = baseline
ON = explicit request renders
AUTO = 合适才渲染
Renderer failure = answer still completed
Artifact = refresh/history available

浏览器 Final Gate 至少：
20 个普通问答
10 个文字 Solver
10 个图片 Solver
10 个 Circuit Render
5 个多图 Circuit
5 个追问

质量：
normal solver semantic quality >= baseline
unexpected waiting_review = 0 或有明确业务原因
hard degrade regression = 0
same question contradiction = 0
circuit OFF regression = 0

性能记录：
text p50/p95
image p50/p95
render p50/p95

必须实际测试：
CIRCUIT_RENDER_ENABLED=false
确认 Circuit 完全退出主流程。

代码质量：
Ruff
Mypy 可运行范围
compileall
Node syntax
git diff --check
relevant pytest

输出：
`docs/audit/56_harness_circuit_final_regression.md`
`docs/audit/57_harness_circuit_stable_baseline.md`
