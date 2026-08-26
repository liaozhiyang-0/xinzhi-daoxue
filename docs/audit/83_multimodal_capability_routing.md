# 83 多模态能力提示与路由

日期：2026-08-26

## 设计

`MultimodalCapabilityHint` 只描述意图、可能能力、CircuitIR 是否需要、触发来源和 reason codes；它不含 `agent_id`，也不替代现有 `TaskRouter` 或 Planner。

## 能力矩阵

| 语义 | Hint intent | 主要能力 | CircuitIR |
| --- | --- | --- | --- |
| 普通看图/未知图像 | `EXPLAIN_IMAGE` / `UNKNOWN` | `general_vision` | 否 |
| 普通题目求解 | `SOLVE_PROBLEM` | `solver`, `general_vision` | 否 |
| 读取文字 | `READ_TEXT` | `text_reading` | 否 |
| 检查学生答案 | `CHECK_MY_WORK` | `student_work_review` | 否 |
| 表格/图表 | `TABLE_ANALYSIS` / `SOLVE_PROBLEM` | `table_analysis` / `chart_analysis` | 否 |
| 波形/频谱 | `WAVEFORM_ANALYSIS` | `waveform_analysis` | 否 |
| 拓扑级电路分析 | `CIRCUIT_ANALYSIS` | `circuit_analysis` | 是 |
| 明确生成/重绘电路图 | `CIRCUIT_RENDER` | `circuit_render` | 是 |

普通图片会进入既有 Solver 生成链；多图保持原上传顺序，复合图片不要求所有图片都满足 CircuitIR。

## 观测指标

新增进程级计数器覆盖多模态任务数、各图片角色、未知角色、CircuitIR 请求/跳过/失败、通用视觉调用、复用观察和重复视觉调用。指标只做观测，不参与路由决策。
