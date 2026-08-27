# 07 Circuit Rendering 强化专项

建立至少 50 个 Circuit Golden Cases，优先来自用户本地真实电路图。

分类：
R/RC/RL/RLC、独立源、受控源、运放、二极管、BJT、MOS、小信号、戴维宁/诺顿、复杂多节点、多图、模糊截图。

评价不能只看 SVG 成功，必须评：
component recall、component type、component value、node preservation、branch connectivity、polarity/direction、label correctness、topology correctness、visual readability。

Failure Injection：
unsupported component、duplicate id、missing port、uncertain value、uncertain connection、disconnected graph、renderer exception、artifact write fail。

任何 Circuit failure 都不能影响 Solver 正文。

AUTO 专项：
应触发 30，不应触发 30，统计 TP/FP/FN。AUTO 第一目标是低误触发，不是触发越多越好。

浏览器视觉重点：
SVG 尺寸、标签重叠、元件重叠、连线穿透、箭头/极性、长 label、dark mode、宽度溢出、zoom/expand。

Artifact 必须验证 refresh/session reload/history/restart 后仍可显示。

输出：
`docs/audit/73_circuit_stress_report.md`
