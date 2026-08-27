# 芯智导学：Harness Maturity + Circuit Rendering Integration v1

基线固定为 `5cb699c`。

目标：在不重写现有 Unified Ingress → GoalContract → Planner → CanonicalPlan → Runtime 主链的前提下，以旁路增强方式加入 Trace、Semantic Eval、CapabilitySpec 和 Circuit Rendering。

核心规则：
1. 不重写 Planner / Runtime。
2. 不引入 LangGraph、AutoGen、CrewAI、Semantic Kernel 替换现有框架。
3. 不新增 Circuit Agent；绘图只能作为 Tool / Capability。
4. 每阶段独立验证、独立 commit。
5. 每阶段都做 `/workspace` 浏览器 smoke。
6. Circuit 必须有 Feature Flag。
7. Renderer 失败绝不能导致 Solver 失败。
8. 前一阶段未稳定，不进入下一阶段。

执行顺序：
H0 Baseline Freeze
→ H1 Trace Projection
→ H2 Semantic Eval
→ H3 CapabilitySpec
→ C0 Circuit Standalone
→ C1 Circuit OFF/ON
→ C2 SVG Artifact
→ C3 AUTO Policy
→ C4 Browser Acceptance
→ H4 Tool Guard Pilot
→ R Final Regression
→ Git Closeout

本阶段明确不做：MCP、ngspice、Lcapy、SKiDL、CircuitJS、KiCad、Swarm、GroupChat、Critic Agent 群、复杂 Sandbox、分布式 Runtime、新 Memory 框架、新 DAG DSL。
