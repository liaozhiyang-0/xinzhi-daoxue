# 芯智导学 Phase F 总目标：Evaluation → Failure Analysis → Improvement Proposal → Offline Replay → Promotion

## 阶段定位
Phase B-E 已完成 Planner、Skill Framework、Reflection 和 Experience Memory。Phase F 不再新增智能控制层，而是把已有 Evaluation、Trace、Planner/Skill/Reflection/Experience 记录收敛为一个可重复、可归因、可对比、可提出改进候选并通过离线回放验证的优化闭环。

目标：
```text
Task / Runtime / Planner / Skill / Reflection Trace
                     ↓
               Evaluation
                     ↓
            Failure Attribution
                     ↓
          Failure Pattern Aggregate
                     ↓
          Improvement Proposal
                     ↓
             Offline Replay
                     ↓
       Regression / Cost / Safety Gate
                     ↓
          Human / Policy Approval
                     ↓
       Experience / Skill / Planner Candidate
```

Phase F 只产生“可审核的改进候选”，不自动修改 Prompt、Skill、Planner、Router、代码或生产配置。

## 从 Phase E 带入的边界
1. Experience Memory 当前是 `STRUCTURAL_GO / CONDITIONAL_GO`，未证明真实 Provider 答案质量提升。
2. Experience Planner prior 默认保持 OFF / allowlist / fail-safe baseline。
3. Provider-free / synthetic evidence 不得当作生产质量证据。
4. Full backend suite 仍存在 6 个已知、与 Experience 无关的失败；Phase F 必须建立 baseline accounting。
5. Phase F 优先接入此前 336-case 全量测试，而不是另造一套小型测试。
6. Phase F 开始前必须确认 Phase E final release 已 push 到 GitHub，并记录 CI 状态。

## 非协商原则
1. 复用现有 EvaluationCase / EvaluationRunner / Scorer / report，不创建第二套 Evaluation Framework。
2. 复用现有 Task/Runtime/Planner/Skill/Reflection/Experience trace，不创建第二 Trace 系统。
3. Failure Analysis 必须基于可观察 evidence。
4. Improvement Proposal 只是 candidate，不自动生效。
5. Offline Replay 必须与 baseline 使用相同 case、模型/Provider 条件和评分协议。
6. 不允许为了 GO 临时降低阈值。
7. Mock/synthetic/offline/real-provider/canary/production evidence 必须分层。
8. Evaluation 结果不能自动改代码、Prompt、Skill、Planner policy、Tool policy。
9. Promotion 必须经过 approval / governance。
10. 不新增 public Agent，不创建第二 Runtime。
11. 优先接入此前 336-case 全量测试体系。
12. F0-F7 本地连续执行，不逐阶段 commit/push。
13. 只有整个 Phase F 完成后统一一次大阶段 commit + push + GitHub Actions。

## 执行顺序
1. F0_phase_e_release_checkpoint.md
2. F1_existing_evaluation_audit_and_contract.md
3. F2_trace_level_scoring_and_failure_taxonomy.md
4. F3_failure_attribution_and_pattern_aggregation.md
5. F4_improvement_proposal_framework.md
6. F5_offline_replay_and_counterfactual_evaluation.md
7. F6_experience_and_promotion_governance.md
8. F7_full_suite_and_real_evidence_campaign.md
9. F8_phase_f_closeout_and_git_release.md

## 总退出条件
- Phase E release 已远端保存；
- 现有 Evaluation Framework 成为唯一 owner；
- evaluation 能绑定 task/run/trace/planner/skill/reflection/experience version；
- failure taxonomy 统一；
- failure attribution 有 evidence；
- failure pattern 可跨 case 聚合；
- ImprovementProposal contract 完整且不自动生效；
- offline replay 可对 baseline/candidate 做公平比较；
- regression/cost/safety gate 完整；
- promotion 与 Experience governance 对接；
- 336-case 或等价代表性全量集纳入；
- 至少一组真实历史失败案例参与评测；
- synthetic 与真实 evidence 分级；
- 不自动改 Prompt/Skill/代码；
- Phase F final release 已 push，GitHub CI 状态已记录。
