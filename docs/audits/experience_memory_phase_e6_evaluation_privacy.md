# Phase E6：Evaluation、Privacy、Conflict 与 Forget

## 已验证控制

| 维度 | 控制/结果 |
| --- | --- |
| Retrieval | 只返回 active、未过期、scope/version compatible；top-k 有界，按 capability/course/problem/skill/risk 确定性评分 |
| Planner impact | 默认 shadow-only；prior disabled、allowlist 不命中、证据不足或异常时返回 baseline |
| Quality | Success 需要 verification/no-critical-regression；Strategy 需要多样本或 high-quality eval；Failure 只作 warning，不作单次永久封禁 |
| Provenance | candidate 强制 trace/run/eval 至少一个 source ID；记录 planner/plan/skill/tool/model version |
| Privacy | raw prompt/answer/content/message/attachment 等键被移除；user-scoped 必须 owner 匹配；global 必须 deidentified |
| Lifecycle | explicit validate/approve/activate、reject、deprecate、expiry、user-scoped forget；forgotten 不再被 Retriever 返回 |
| Runtime compatibility | 不创建 Task、不执行 Agent、不修改 checkpoint；forget 不改变历史 checkpoint/resume 语义 |

## Conflict 规则

如果 active 记录显式 `conflicts_with`，Retriever 排除冲突组，并保留 `last_conflicts` 供 audit；不会静默任选一条策略。后续可基于 evidence、version、适用性、recency 和 validation quality 进行人工/离线裁决，当前无法裁决时采用 no-experience baseline。

## Evaluation report

新增结构化 `ExperienceEvaluationReport`，覆盖 valid/irrelevant match、stale/scope/version filtering、planner improvement/degradation、failure avoidance、invalid target、privacy leakage 和 provenance completeness。当前仓库没有真实 Provider 质量数据，因此结论限定为：

```text
STRUCTURAL_GO for contract/lifecycle/privacy/isolation controls
CONDITIONAL_GO for real planner quality improvement
```

不得宣称 Experience Memory 已提升真实答案质量。

## E6 状态

`PASS (STRUCTURAL_GO / CONDITIONAL_GO)`。安全边界、回退路径、隐私隔离和生命周期语义已具备；真实 Provider 价值仍需后续受控评测。
