# 81 多模态 Gate 审计

日期：2026-08-26
分支：`feature/circuit-capability-v1`

## 结论

本次收敛把“图片可接收”“通用视觉理解”和“CircuitIR 专用资格”分成三层，未改动 Unified Ingress、GoalContract 所有权、Planner 所有权、CanonicalPlan、TaskExecutionCoordinator、RuntimeTaskEngine、ProductionExecutionManifest 或冻结基线。

## 现有数据流

`TaskCreationService` 仍负责非阻塞创建、统一请求准备和排队；`UnifiedRequestPreparationService` 现在只增加角色与能力提示；`PlannerService` 仍是计划唯一构造点；`AcademicProblemSolverService` 复用既有图片 composer、Provider HTTP 链和 Solver boundary。

## Gate 变化

| Gate | 普通图片 | 拓扑级电路任务 |
| --- | --- | --- |
| 上传/附件接受 | 保持原校验 | 保持原校验 |
| 多模态语义提示 | `general_vision` 等 capability hint | 增加 `circuit_analysis` hint |
| 视觉提取 | 可读摘要即可继续 | 仍要求专用结构化拓扑才能计算/判断 |
| CircuitIR | 不请求 | 仅显式渲染、拓扑分析、Solver topology hint 或 `SOLVE_VERIFY_RENDER` 请求 |
| CircuitIR 失败 | 不影响普通 Solver | 只阻断可视化/拓扑专用分支，保留边界说明 |

## 风险与边界

- 未增加新的 Agent，也未把视觉推断直接写成 CircuitIR。
- `SolverBoundaryPolicy` 默认严格行为保留，只有实际请求链传入专用拓扑提示时才启用该 gate。
- 图片角色是可解释元数据，不是固定路由；未知角色默认通用视觉理解。
- 原始图片内容不写入观测契约，只保留有限摘要、角色和引用 ID。
