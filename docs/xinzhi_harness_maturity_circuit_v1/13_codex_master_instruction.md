# Codex 总执行指令

阶段：Harness Maturity + Circuit Rendering Integration v1

基线：`5cb699c`

这是极其保守的旁路增强阶段。

最高要求：
绝不能因为 Harness 成熟度增强或 Circuit Rendering 接入，破坏当前稳定主线回答能力。

严格顺序：
H0 → H1 → H2 → H3 → C0 → C1 → C2 → C3 → C4 → H4 → R

禁止跳阶段。

不要：
- 重写 Planner
- 重写 Runtime
- 新增 Circuit Agent
- 引入 LangGraph/AutoGen/CrewAI/Semantic Kernel 替代系统
- 新建第二套 Task queue
- 新建第二套 Evaluation
- 新建第二套 Memory
- 一次改多个核心执行层

H0 必须先记录 5cb699c baseline。
每阶段确认文字 Solver、图片 Solver、六场景未退化。

Harness：
H1 Trace 只能是只读 projection。
H2 Semantic Eval 扩展现有 evaluation。
H3 CapabilitySpec 只增加 metadata。

Circuit：
必须复用现有 CircuitIR、validator、layout、renderer、tool。
Circuit Drawing 是 Tool/Capability，不是 Agent。

推荐：
Solver → Verify → optional circuit.render → Artifact → Presentation

Renderer 永远不是 Solver success gate。

Feature Flags：
CIRCUIT_RENDER_ENABLED
CIRCUIT_RENDER_AUTO

第一阶段 false/false；
C1 后 true/false；
只有 C3 通过后才 true/true。

Render Mode：
先 OFF/ON，后 AUTO。

SVG：
必须走 Artifact Store，不能塞进 answer_text、prompt、memory。

浏览器：
每个影响用户路径的阶段必须在 `http://127.0.0.1:8000/workspace` 真实测试。
不能仅凭后端 pytest 判定完成。

真实题：
优先使用本地已有电路题、电路图、教材截图、多图题、历史人工复测题。

Circuit 任何 parse/validate/render/artifact 失败，只影响 Circuit Artifact，不得影响正常 Solver 结果。

每阶段单独 commit。任何阶段失败立即 STOP，修好后再继续。

最终生成：
docs/audit/46_harness_circuit_baseline.md
docs/audit/47_trace_projection_report.md
docs/audit/48_semantic_eval_report.md
docs/audit/49_capability_spec_report.md
docs/audit/50_circuit_standalone_report.md
docs/audit/51_circuit_runtime_integration_report.md
docs/audit/52_circuit_artifact_report.md
docs/audit/53_circuit_auto_policy_report.md
docs/audit/54_circuit_browser_acceptance.md
docs/audit/55_tool_guard_pilot_report.md
docs/audit/56_harness_circuit_final_regression.md
docs/audit/57_harness_circuit_stable_baseline.md

最终向用户汇报：
baseline commit
phase commits
final HEAD
tests passed/failed/skipped
browser E2E count
Trace status
Semantic Eval status
Circuit OFF/ON/AUTO results
render success rate
artifact restore result
normal Solver regression result
remaining risks
working tree status

最终成功定义：
在不破坏 5cb699c 稳定主线的情况下，增加 Trace、Semantic Eval、CapabilitySpec，并把 Circuit Rendering 作为可关闭、可回滚、可观察、可评测的专业 Capability 安全接入。
