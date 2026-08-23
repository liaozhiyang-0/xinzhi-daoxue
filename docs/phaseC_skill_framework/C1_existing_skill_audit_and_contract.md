# Phase C1：现有 Skill 审计与 Contract 定义

## 目标
审计仓库已有 Skill 实现，禁止重复造轮子。

## 重点检查
- `apps/api/app/services/skill_registry.py`
- `config/skills/*.yaml`
- RouteDecision.selected_skills
- IntentExecutionPlan / CanonicalPlan skill 字段
- Teaching Foundation skill 使用
- Academic Solver / Research / Knowledge 中已有 skill-like worker
- Skill 相关 tests / evaluation

## 输出分类
KEEP / EXTEND / ADAPT / FREEZE / REMOVE LATER

## SkillDefinition 至少表达
skill_id、version、name、description、domain/course、capability_ids、problem_types、prerequisites、input/output contract、eligible workers/tools、required evidence、risk、budget hint、verification requirements、keywords/semantic description、status。

## SkillMatch 至少表达
skill_id、score、match_reasons、eligibility、prerequisite_status、policy_status、version。

## 禁止
不实现 semantic vector retrieval，不接入真实 Planner 路径，不执行 Skill，不实现 SkillMemory，不新增 public Agent。

## Git
commit: `feat(agent): define phase C skill contracts`
push 当前 Phase C 分支。

## 结束条件
唯一 Skill identity / contract / owner 明确并通过测试后停止。
