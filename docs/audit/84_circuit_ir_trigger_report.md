# 84 CircuitIR 触发报告

日期：2026-08-26

## 触发条件

CircuitIR 只在以下条件之一成立时请求：

1. 用户明确要求画、生成、重绘、渲染电路图；
2. 用户进行带拓扑语义的电路分析，例如节点、支路、网孔、等效电路或节点电压；
3. Planner hint 明确 `requires_topology` / `solver_requires_topology`；
4. 计划模式为 `SOLVE_VERIFY_RENDER`。

仅有图片、`CIRCUIT_DIAGRAM` 角色、课程为 CT、或文本中出现普通“电路”字样，不足以单独请求 CircuitIR。

## 决策结果

`CircuitVisualizationDecision` 新增 `multimodal_intent`、`circuit_ir_requested` 和 `trigger_source`。没有请求时结果为 `SKIP` 且 `blocked=false`，不会把普通图片误报为拓扑阻断；请求但 IR 缺失时保留 `CIRCUIT_IR_UNAVAILABLE`，渲染节点仍为 optional/nonfatal。

## 保留的安全行为

- `extract_circuit_ir` 仍只接受可信结构化 `CircuitIR`，不从图片或自由文本直接生成 IR。
- controlled allowlist、复杂度预算、critical uncertainty 和非致命渲染观测保持不变。
- Solver 拓扑边界仍拒绝未形成可核验结构的专用电路计算。
