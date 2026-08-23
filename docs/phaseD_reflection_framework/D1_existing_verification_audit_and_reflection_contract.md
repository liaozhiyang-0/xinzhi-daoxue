# Phase D1：现有 Verification 审计与 Reflection Contract

## 目标
先审计现有检查、review、replan、quality gate，避免重复实现 Critic。

## 重点审计
- Academic Solver 高风险 review / professional validation
- Runtime Controller observe → decide → act → verify
- bounded replan
- RuntimeResultPipeline
- SolverQualityGate
- Knowledge evidence / citation validation
- Research evidence review
- Teaching review / approval
- existing InternalAgentHub reviewers
- AgentResult validators
- Tool/domain deterministic verification

## 分类
KEEP AS DETERMINISTIC VERIFIER / REUSE AS CRITIC WORKER / ADAPT TO REFLECTION CONTRACT / MERGE LATER / FREEZE / REMOVE LATER。

## Contract
统一 `CriticResult` 至少表达：

```text
status: pass | revise | fail | needs_review
issue_types
severity
issue_summary
evidence_refs
unsupported_claims
required_changes
confidence
critic_version
revision_allowed
```

统一 `RevisionRequest / RevisionResult` 至少表达：

```text
original_result
critic_result
allowed_changes
evidence_refs
revision_count
revision_budget
revised_result
change_summary
```

## 原则
CriticResult 是建议，不是最终验证；deterministic/domain verifier 可覆盖 Critic pass；Critic 不得直接改变 terminal state；不新增 public Critic Agent。

## 交付物
reflection audit、contracts、ownership matrix、tests。

## 提交
本阶段不 commit，完成后继续 D2。
