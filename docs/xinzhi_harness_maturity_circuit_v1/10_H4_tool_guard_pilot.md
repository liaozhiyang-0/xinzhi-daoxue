# H4：Tool Guard Pilot（仅 Circuit）

只用 `circuit.render` 试点，不一次改所有工具。

结构：
Tool Request
→ Precondition Guard
→ Tool Execution
→ Postcondition Guard

Precondition：
CircuitIR schema、component count、supported components、port completeness、critical uncertainties、input size。

Postcondition：
result status、validation state、SVG/artifact presence、artifact size、renderer identity、warnings。

Guard 结果建议：
allow
allow_with_warning
reject_tool_only

Circuit Tool 被拒绝时，Solver answer 仍必须返回。

本阶段不要推广到 calculator、RAG、research、shell。

提交：
`feat(tooling): add circuit tool guard pilot`

输出：
`docs/audit/55_tool_guard_pilot_report.md`
