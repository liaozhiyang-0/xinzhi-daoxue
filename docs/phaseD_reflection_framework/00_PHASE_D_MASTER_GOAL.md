# 芯智导学 Phase D 总目标：Reflection / Critic / Bounded Revision

## 1. 阶段定位

Phase C 已完成 Skill Framework 的结构接入。Phase D 的唯一主目标是：

> 在不破坏现有 deterministic/domain verification、Runtime Kernel、Result Pipeline 和 rollback 的前提下，引入统一、受限、可审计的 Reflection 闭环：Generate → Critic → Bounded Revision → Verification → Publish。

本阶段不实现 Experience Memory，不做自动自我改进，不新增 public Agent，不创建第二 Runtime。

目标架构：

```text
Planner / CanonicalPlan
        ↓
Skill / Tool / RAG / Worker
        ↓
Draft Result
        ↓
ReflectionPolicy
   ┌────┴────┐
   ↓         ↓
Skip      Critic
             ↓
       CriticResult
        ┌────┼─────┐
        ↓    ↓     ↓
       pass revise fail/review
              ↓
       Bounded Revision
              ↓
    Deterministic / Domain Verification
              ↓
     Result Governance / Publish
```

## 2. 从 Phase C 带入的限制

1. C6 的 GO 仅为 `synthetic_provider_free` 结构验证，不代表真实 Provider 答案质量。
2. C6 targeted tests 数量较少，不能据此扩大智能控制范围。
3. Controlled Canary 只验证 policy decision，未证明真实线上流量质量。
4. Skill 跨场景复用已证明结构可行，但需继续区分专业内容 Skill 与编排/审核 Worker。
5. Planner / Skill takeover 继续保持 default OFF / allowlist / rollback。
6. Phase D 必须用“Critic 是否发现真实问题、Revision 是否改善结果”评估价值，不能只看 schema 通过。
7. Phase D 开始前必须确认 Phase C 最终大阶段提交已经 push 到 GitHub 且 CI 通过。

## 3. 非协商原则

1. Reflection 不是新的 public Agent。
2. Critic 作为 Internal Worker / internal capability，不占用新的 public Agent ID。
3. 不建立第二 Runtime、第二 Task lifecycle 或第二 checkpoint。
4. Critic 不能直接发布最终答案。
5. Critic 不能绕过 deterministic/domain verification。
6. 数值、单位、工具副作用、权限、引用存在性优先由 deterministic/domain verification 判定。
7. Critic 只能引用已有 evidence / tool observation / trace，不得虚构 evidence。
8. Revision 默认最多 1 次，禁止递归批评循环。
9. Reflection 不是所有任务强制调用，必须由 ReflectionPolicy 按风险/质量/证据/复杂度触发。
10. 低风险简单任务应可直接跳过 Reflection。
11. Critic failure 不得破坏已有 fail-closed Result Pipeline。
12. Phase D 不写 Experience Memory，不自动提升长期策略。
13. 不扩大 public Agent 数量，不拆分 Academic Solver。
14. 不重写 Runtime Kernel。
15. D0-D6 只在本地连续执行，不逐阶段 commit/push。
16. 只有整个 Phase D 完成并通过完整验证后，才统一进行大阶段 Git commit + push + GitHub Actions。

## 4. Git 提交规则

Phase D 期间 D0-D6 不 commit、不 push 半成品。

只有 D7 Closeout 时执行：

```text
git status
git diff --check
ruff
mypy
targeted pytest
full pytest / repository checks
frontend checks where contract changed
git add <Phase D related files only>
git commit -m "feat(agent): complete phase D reflection loop"
git push origin <phase-d-branch>
verify remote SHA
check GitHub Actions
```

若 CI 因 Phase D 回归失败，可追加同属 Phase D release 的最小 `fix(ci)` commit；在 CI PASS 前不得进入 Phase E。

## 5. 执行顺序

1. `D0_phase_c_release_checkpoint.md`
2. `D1_existing_verification_audit_and_reflection_contract.md`
3. `D2_reflection_policy_and_trigger.md`
4. `D3_critic_shadow_mode.md`
5. `D4_bounded_revision_integration.md`
6. `D5_verification_and_publish_gate_integration.md`
7. `D6_reflection_evaluation_and_controlled_canary.md`
8. `D7_phase_d_closeout_and_git_release.md`

## 6. Phase D 总退出条件

- Phase C final release 已在 GitHub 且 CI 通过；
- 现有 verification/review/replan 逻辑已审计，未重复造第二套；
- Critic contract 统一；
- ReflectionPolicy 能决定 skip / critique / review；
- Critic shadow 可观测且不改变真实结果；
- bounded revision 最多一次；
- deterministic/domain verification 仍拥有最终硬门禁；
- Critic 不得虚构 evidence；
- 至少覆盖 Academic Solver、Knowledge、Research，Teaching 视风险接入；
- 低风险任务不会无条件增加 Critic 模型调用；
- evaluation 同时评估 critic precision、revision improvement、degradation、cost/latency；
- 真实 Provider 证据与 synthetic evidence 分级；
- controlled canary default OFF、allowlist、rollback；
- Phase D 最终大阶段 commit 已 push；
- GitHub Actions CI PASS；
- Phase E Experience Memory 未开始。
