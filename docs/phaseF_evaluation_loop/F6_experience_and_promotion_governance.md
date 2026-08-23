# Phase F6：Promotion Governance 与 Experience 对接

## 目标
把通过 replay 的 Proposal 接入现有 Experience governance，而不是自动修改系统。

## 可进入 Experience candidate
- validated failure pattern
- validated strategy evidence
- replay result
- safe fallback observation

## 不能自动进入生产配置
- prompt_candidate
- planner policy
- skill configuration
- verification rules
- reflection policy
- tool binding

## PromotionDecision
至少：
```text
proposal_id
replay_result_id
status: approve | reject | defer | needs_review
eligible_targets
evidence_level
regression_summary
risk
approval_reason
reviewer/policy
rollback_requirement
```

通过验证的 Proposal 可以创建 Strategy / Failure / Success Experience candidate，但仍必须走 Phase E 的 candidate → validated → approved → active。

Phase F 不允许自动写代码。

## 本阶段不 commit
完成后继续 F7。
