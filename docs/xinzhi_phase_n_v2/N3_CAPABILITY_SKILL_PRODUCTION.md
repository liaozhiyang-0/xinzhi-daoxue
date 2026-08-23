# N3：Capability / Skill 生产化

## 目标

把“固定 Agent 选择”转成 Capability + Skills。

## 六案例 Capability 映射

建议：

- TP-01 → `teaching.lesson_design`
- FE-01 → `teaching.assignment_review` + `learning.first_error_diagnosis`
- LP-01 → `learning.path_plan`
- RB-01 → `research.evidence_brief`
- KG-01 → `knowledge.govern`
- AC-01 → `academic.solve` + `vision.circuit_parse`

具体名称按现有 registry 调整。

## Skill 示例

course_goal_alignment
differentiated_practice
formative_assessment
first_error_diagnosis
learning_dependency_analysis
evidence_brief
knowledge_asset_review
circuit_image_parse
analog_feedback_analysis
saturation_check

## 规则

- Capability 必须注册；
- Skill 必须注册且 policy pass；
- Planner 不得自创；
- 未知 capability fail-closed；
- fixed Agent ID 只保留 alias / trace / migration compatibility。

## Binding

建立或强化：

CapabilityBindingRegistry
SkillBindingRegistry

禁止继续新增：

`if agent_id == ...`

本阶段不 commit。
