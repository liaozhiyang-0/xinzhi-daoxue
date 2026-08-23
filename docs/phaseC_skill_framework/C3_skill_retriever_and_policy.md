# Phase C3：SkillRetriever 与 SkillPolicy

## 目标
建立“从注册技能中选技能”的能力，确定性优先、可审计、bounded。

## Retriever 输入
CanonicalGoal、course、intent、problem_type、capability、context summary、evidence state、learner state（按需只读）、budget/risk。

## 输出
bounded top-k SkillMatch。

## 检索策略
优先 exact capability、course/domain、problem type、prerequisites、keywords、registry metadata、deterministic score。
如复用现有 embedding 成本很低，可在 feature flag 后做 optional semantic rerank，必须有 deterministic fallback。

## SkillPolicy
检查 registered、version、status、capability/course、prerequisites、tool/worker dependencies、evidence、risk、budget、role/permission。

## Fail-closed
拒绝未注册 ID、非法版本、禁用状态、前置条件不满足、依赖不可用、风险超限。

## 禁止
Retriever 不执行 Skill、不调用 Runtime、模型不能发明 Skill ID、不实现 SkillMemory。

## Git
commit: `feat(agent): add bounded skill retrieval and policy`
push 当前 Phase C 分支。

## 结束条件
Retriever + Policy 独立测试通过，非法 Skill 能 fail-closed 后停止。
