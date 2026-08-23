# Phase C4：Planner × Skill Shadow Integration

## 目标
让 Planner 能选择 registered skills，但先只进入 shadow/trace，不影响默认真实执行。

## 路径
Planner → SkillRetriever → SkillPolicy → selected_skills → CanonicalPlan → TRACE ONLY

## 必须完成
- Planner 只能引用 Registry Skill；
- snapshot/CanonicalPlan 记录 ID、version、match reason、policy result；
- 对照旧 RouteDecision.selected_skills；
- 记录 selection/rejection/empty reason；
- 扩展 Phase B 典型场景的 Skill shadow evidence；
- 重点检查 Academic Solver、Knowledge、Teaching、Research 的 Skill 选择。

## 禁止
不直接改变 Runtime，不扩大 Planner canary，不删除旧字段，不实现 Critic，不写 Experience Memory。

## Git
commit: `feat(agent): integrate skill selection in planner shadow`
push 当前 Phase C 分支。

## 结束条件
Skill selection 可追踪、可拒绝、可比较，但未接管 Runtime 后停止。
