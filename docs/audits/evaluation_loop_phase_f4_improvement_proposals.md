# Phase F4：Improvement Proposal Framework

## Contract

`ImprovementProposal` 包含：

```text
proposal_id, source_pattern_ids, proposal_type, target_component,
target_version, problem_statement, proposed_change, expected_effect,
success_metrics, risk, estimated_cost, required_cases, rollback_plan,
evidence_refs, status
```

支持 planner policy、skill metadata/selection、tool binding、RAG policy、verification、reflection、experience strategy、prompt candidate、fallback、fixture 和 infrastructure 等类型。

## 生命周期

```text
draft → reviewed → replay_ready → validated → approved / rejected / deferred → promoted
```

`ImprovementProposalService` 只校验来源 pattern、生成 candidate contract 和受控状态转移；没有代码写入、Prompt 写入、Skill/Planner policy 修改或自动提交。

只允许从 `aggregation_eligible` pattern 创建 proposal；proposal 必须列出 required cases、success metrics、risk 和 rollback plan。

## F4 结论

Failure Pattern 到可审核候选的边界已形成；F4 完成。
