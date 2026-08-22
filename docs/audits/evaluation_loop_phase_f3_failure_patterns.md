# Phase F3：Failure Attribution 与 Pattern Aggregation

## 聚合实现

`FailurePatternAggregator` 按以下维度生成确定性 key：

```text
course, task_family, problem_type, capability, skill, tool,
planner_version, model/provider, failure stage, error code,
input mode, evidence quality
```

pattern 保存 occurrence、case/failure IDs、evidence level counts、evidence refs、reproducible rate 和 guardrails。

## 防止错误泛化

- `infrastructure`、`fixture`、provider error 和 timeout 仍可报告，但不会被标为长期 strategy evidence；
- 单次观察会带 `single_observation_requires_reproduction`；
- synthetic-only 会带 `synthetic_evidence_cannot_claim_production_quality`；
- 只有非瞬时、可复现且至少两次观察的 pattern 才标记 `generalizable=true`；
- 模型归因 worker 未启用，当前只使用可审计 deterministic attribution。

## 336-case 接入边界

公开仓库评测目录当前通过 `scripts/run_evaluation.py --validate-only` 校验出 84 cases，覆盖 AE/CT/DE/SS 及现有 suite。此前私有 `真实测试题/统一格式/balanced_336/all_cases.json` 不在当前工作区，未复制或伪造；loop CLI 支持在该 catalog 提供后用同一 `EvaluationRecord` 入口接入。

另导入 6 个已有历史超时 case 的脱敏元数据，来源为 `docs/optimization/targeted_solver_test_report_v1.md`，作为 offline historical evidence；不含题面、答案或 prompt。

## F3 结论

单 case failure 已可聚合为带 evidence/guardrail 的 failure pattern；F3 完成，336 私有数据缺口保留为 conditional evidence。
