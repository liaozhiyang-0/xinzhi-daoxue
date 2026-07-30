# SolutionPacket v1

`SolutionPacketV1` 是既有 `SolverResult` 的教学适配合同，不替换
`final_answer`，也不会再次执行 Solver。

## 字段语义

- `course_id`、`problem_type`：来自实际求解结果。
- `givens`、`targets`、`assumptions`：直接适配已有结构化字段。
- `skill_ids`：由版本化 SkillRegistry 映射；不确定时为空并标记 `partial`。
- `plan`、`steps`：来自已有 solution method/steps。稳定步骤 ID 使用 `S1`、
  `S2` 等；`depends_on` 只引用包内步骤。
- `final_answer`、`units`、`common_errors`：来自当前结果，不生成新答案。
- `evidence_refs`、`tool_outputs`：只引用当前执行链已经产生的证据和工具输出。
- `mapping_status`：`mapped`、`partial` 或 `unavailable`。

`step_source="solver_execution"` 表示步骤来自真实求解执行结果，不能包装成
专门设计的教学步骤。只有未来真正的教学编排器生成的步骤才能标为
`pedagogical`。

## 降级规则

适配器遇到缺少步骤、未知课程、未知题型或不完整结构时保留可验证字段，并在
`warnings` 说明缺口。它不得补写方程、单位、假设或引用，也不得把执行节点名
伪装成学生可读推理。
