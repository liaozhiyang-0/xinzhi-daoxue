# Phase C5：Runtime Skill Binding

## 目标
让 CanonicalPlan 中已批准 Skill 绑定到现有 Runtime 能力，不建立新的 Skill Runtime。

## 原则
Skill ≠ Runtime ≠ Agent。

Skill 只能解析为现有 Runtime Handler、Tool、Internal Worker、RAG step 或 Business Capability adapter。

## 必须完成
- SkillBinding / SkillExecutionDescriptor；
- skill_id/version → handler/tool/worker/capability operation；
- binding 经 Registry + Policy；
- Runtime 继续执行 AgentRunPlan；
- skill metadata 进入 node、trace、metrics、failure；
- side-effect/approval/timeout/retry 沿用现有 Runtime policy；
- 不建立第二 checkpoint。

## 复用证明
至少一个 Skill 在两个合理上下文中复用；不为了验收强行复用。

## Academic Solver
至少一组 CT Skill 形成：
problem classification → skill selection → tool/worker binding → solver → deterministic verification。

## Git
commit: `feat(agent): bind registered skills to runtime handlers`
push 当前 Phase C 分支。

## 结束条件
Runtime 可执行批准的 Skill binding，且没有新增执行引擎后停止。
