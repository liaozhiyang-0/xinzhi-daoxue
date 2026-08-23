# 芯智导学 Phase E 总目标：Experience Memory

## 1. 阶段定位

Phase D 已完成受限 Reflection 闭环：
Generate / Existing Verification → ReflectionPolicy → Internal Critic → One Bounded Revision → Re-verification → Governance。

Phase E 的唯一主目标是：

> 建立一个可治理、可追溯、可版本化、可遗忘、可评估的 Experience Memory，使 Planner 能参考经过验证的成功/失败/策略经验，但绝不允许经验绕过 Registry、SkillPolicy、ToolPolicy、EvidencePolicy 或 Runtime 验证。

Phase E 不是“让模型自动学习自己”，而是建立一条受控经验生命周期：

```text
Trace / Evaluation / Reflection
          ↓
   Experience Candidate
          ↓
    Governance / Redaction
          ↓
 Offline Validation / Replay
          ↓
 Promotion / Approval
          ↓
 Experience Memory
          ↓
 Planner Retrieval (bounded prior)
          ↓
 Registry / SkillPolicy / Runtime
```

## 2. 从 Phase D 带入的限制

1. Phase D6 只有 `synthetic_provider_free` 证据，结论为 `CONDITIONAL_GO`。
2. Critic / Revision 还没有证明真实 Provider 的质量提升。
3. ReflectionTrace 可以作为 Experience candidate 的来源，但不能自动写成成功策略。
4. Phase D 全量测试存在 6 个无关失败；Phase E 不得掩盖这些问题，也不得把它们算作 Experience Memory 回归。
5. Planner/Skill/Reflection 的 takeover 仍应保持 default OFF / allowlist / rollback。
6. Phase E 不得自动修改 prompt、Skill、Router、Planner policy 或 Tool policy。
7. Phase E 开始前必须确认 Phase D final release 已 push 到 GitHub 且 CI 状态明确。

## 3. 非协商原则

1. Experience Memory 与用户长期 Memory、Session、Learning State 必须分离。
2. 不建立 SuccessMemory / FailureMemory / StrategyMemory 三套独立数据库；统一使用一个 `ExperienceRecord`，通过 projection/view 区分。
3. Experience Record 必须绑定 trace/run/plan/skill/tool/model/version。
4. 未经评测或 promotion 的记录只能是 candidate，不能影响 Planner 默认决策。
5. Mock / synthetic 结果不能被提升为真实成功经验。
6. 失败记录不能被误读为成功策略。
7. Planner 读取 Experience 只能作为候选 prior，不能绕过 Registry / SkillPolicy / ToolPolicy / EvidencePolicy。
8. 不允许跨用户泄露个人数据。
9. 默认不存完整原始学生答案、敏感文本、个人标识；优先保存脱敏特征、策略摘要、错误类型和结构化证据。
10. 经验必须具备 TTL / expiry / conflict / deprecation / forget 能力。
11. Experience Memory 不直接执行任务、不创建 Runtime、不拥有 Task lifecycle。
12. 不实现“自动自我修改 prompt/Skill/代码”。
13. 不新增 public Agent。
14. 不重写 Runtime Kernel。
15. E0-E6 期间不逐阶段 commit/push。
16. 只有整个 Phase E 完成并通过完整验证后，才统一一次大阶段 commit + push + GitHub Actions。

## 4. 经验类型

统一 `ExperienceRecord` 下提供三种 projection：

### Success
记录已验证的 plan/skill/tool strategy、适用条件、结果质量、成本/延迟、evidence level 和版本，不直接存完整答案。

### Failure
记录 failure stage、error code、critic/verification issue、rejected reason、retry/revision outcome、trigger condition。

### Strategy
记录抽象执行策略、前置条件、适用 capability/course/problem type、known success/failure evidence、budget/risk、version。

Strategy 必须来自评测后的 promotion，不允许模型直接自称“这是最佳策略”。

## 5. 生命周期

```text
observed
  ↓
candidate
  ↓
validated
  ↓
approved
  ↓
active
  ↓
deprecated / expired / forgotten
```

建议保留 `rejected` 状态。

只有 active experience 才能进入 Planner retrieval。

## 6. Git 规则

Phase E 内：

- E0-E6 本地连续完成；
- 不逐阶段 commit/push；
- 如中途停止，保留工作树；
- 不做 destructive cleanup。

只有 E7 执行：

```text
git status
git diff --check
ruff
mypy
targeted tests
full pytest / repo checks
git add <Phase E related files only>
git commit -m "feat(agent): complete phase E experience memory"
git push origin <phase-e-branch>
verify remote SHA
check GitHub Actions
```

若 CI 因 Phase E 回归失败，可追加一个最小 `fix(ci)` commit。

## 7. 执行顺序

1. `E0_phase_d_release_checkpoint.md`
2. `E1_memory_and_trace_audit.md`
3. `E2_experience_record_and_governance_contract.md`
4. `E3_experience_write_and_promotion_pipeline.md`
5. `E4_experience_retriever_and_planner_shadow.md`
6. `E5_controlled_planner_prior_integration.md`
7. `E6_experience_evaluation_privacy_and_forgetting.md`
8. `E7_phase_e_closeout_and_git_release.md`

## 8. Phase E 总退出条件

只有同时满足：

- Phase D release 已远端保存；
- Experience Memory 与 user/session/learning memory 清晰分离；
- `ExperienceRecord` 是唯一统一 contract；
- Success/Failure/Strategy 只是 projection；
- candidate / validated / approved / active promotion 完整；
- synthetic/mock 不能升级成真实经验；
- Experience retrieval 是 bounded top-k；
- Planner 只把经验作为 prior；
- Registry / SkillPolicy / ToolPolicy / EvidencePolicy 仍拥有最终资格门；
- 经验具备 provenance、version、TTL、conflict、forget；
- 跨用户数据隔离测试通过；
- 不存不必要的原始敏感文本；
- 有离线 replay / regression 证明经验没有系统性劣化；
- 真实质量证据与 synthetic evidence 分级；
- 没有自动改 prompt/Skill/代码；
- Phase E final commit 已 push，CI PASS；
- Phase F Evaluation Loop 尚未启动。

Phase E 完成后进入：

> Phase F：Evaluation → Failure Analysis → Improvement Proposal → Offline Replay → Promotion
