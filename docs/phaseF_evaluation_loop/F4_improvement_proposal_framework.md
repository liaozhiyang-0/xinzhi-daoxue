# Phase F4：Improvement Proposal Framework

## 目标
让 Failure Pattern 产生“可审核、可回放”的改进候选，而不是直接修改系统。

## ImprovementProposal
至少：
```text
proposal_id
source_pattern_ids
proposal_type
target_component
target_version
problem_statement
proposed_change
expected_effect
success_metrics
risk
estimated_cost
required_cases
rollback_plan
evidence_refs
status
```

## Proposal type
planner_policy / skill_metadata / skill_selection / tool_binding / rag_policy / verification_rule / reflection_policy / experience_strategy / prompt_candidate / fallback_policy / test_fixture / infrastructure

## 生命周期
draft → reviewed → replay_ready → validated → approved / rejected / deferred → promoted

模型生成 Proposal 时必须引用 failure pattern/evidence，不直接写生产配置，不自动提交代码，不自动 promotion。

优先最小改动，不允许用“重写整个 Agent”替代具体问题定位。

## 本阶段不 commit
完成后继续 F5。
