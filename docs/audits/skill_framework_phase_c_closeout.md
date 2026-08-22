# Skill Framework Phase C Closeout

## 最终架构

```text
User Goal
  ↓
Supervisor (API normalization / compatibility / trace envelope)
  ↓
TaskRouter (deterministic preflight)
  ↓
PlannerService
  ↓
SkillRetriever → SkillPolicy → authoritative SkillRegistry
  ↓
CanonicalPlan (selected_skills / skill_selection / skill_bindings)
  ↓
SkillBindingService → existing RuntimeHandlerRegistry
  ↓
CanonicalPlanAdapter → Runtime Kernel
  ↓
existing Tool / Worker / RAG / Academic Solver
  ↓
Verification / Governance / Result Commit
```

持久化和审计边界为 Registry/config、CanonicalPlan、Runtime Plan/Checkpoint、trace/event
以及 Skill evaluation report。`OverallRoutingService` 只作为显式旧链路兼容包装器保留，
不参与 Planner takeover 的默认路径。

## KEEP / MERGE / FREEZE / REMOVE

| 处理 | 对象 | 结论 |
| --- | --- | --- |
| KEEP | authoritative SkillRegistry、SkillRetriever、SkillPolicy | 唯一 Skill 控制面 |
| KEEP | PlannerService、CanonicalPlan、Runtime Kernel、Checkpoint/Recovery | 现有控制和执行边界 |
| KEEP | RuntimeHandlerRegistry、Tool/Worker/RAG、Academic Solver | Skill 只绑定既有能力 |
| KEEP | Task API、AgentRequest/Result、RAG/Tool 接口、Planner rollback | 兼容性边界 |
| MERGE | Planner 的 Skill selection 与 CanonicalPlan | 选择结果只有一个权威落点 |
| MERGE | SkillBindingService 与 Runtime Plan adapter | 统一 skill@version → handler 映射 |
| FREEZE | Overall Router、InternalAgentHub 扩张、public Agent 数量、canary 自动扩容 | 仅兼容/存量能力，不继续扩张 |
| FREEZE | Reflection、SkillMemory、真实 Provider 质量结论 | 不属于 Phase C |
| REMOVE | 第二 SkillRegistry、第二 Runtime、Skill-owned task lifecycle、Skill 内 Provider 调用 | 当前实现中不允许存在 |
| REMOVE | 为每个 Skill 新增 public Agent 或复制 Academic Solver | 保持 Academic Solver 边界 |

## 收口检查

- Registry：C2 的 authoritative `SkillRegistry` 被 C3-C6 复用，未新增第二实现。
- Runtime：C5/C6 只使用现有 `RuntimeHandlerRegistry`、adapter 和 Runtime Kernel，未新增
  第二 Runtime 或 Skill-owned lifecycle。
- Agent：没有新增 public Agent；Worker 仍是 Internal Worker。
- Planner：只能从 Registry/Policy 通过的 Skill 写入 CanonicalPlan；takeover 仍 default OFF、
  allowlist gated，并保留 rollback。
- Trace/evaluation：selected skill、binding、version 和拒绝码进入 plan/runtime metadata 和
  evaluation report；CT/KCL 形成可审计链。
- Reuse：CT skill 可由 Academic Solver/Planner 计划路径复用到 Teaching 前置技能链，绑定同一
  既有 Tool/Handler，不复制执行实现。
- Evidence：provider-free 结构证据与真实 Provider/production 证据分级记录；C6 不宣称答案质量。
- Phase D：未开始。

## Git 与验证约定

C0-C5 的既有提交已在 Phase C 分支远端。根据本次执行指令，C6/C7 不再分别提交；全部 C
阶段任务完成后统一使用最终提交 `feat(agent): complete phase C skill framework`，再执行
本地测试、`git diff --check`、push、GitHub Actions 和 remote SHA 校验。该 closeout 在最终
CI 通过后视为完成。
