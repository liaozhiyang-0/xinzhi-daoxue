# Phase F1：现有 Evaluation 审计与统一 Contract

## Owner 分类

| 组件 | 分类 | 结论 |
| --- | --- | --- |
| `EvaluationCaseLoader` | AUTHORITATIVE / REUSE | 继续作为 case catalog 唯一入口 |
| `EvaluationRunner` | AUTHORITATIVE / REUSE | 继续负责现有 Task/Runtime 执行，不复制 runner |
| `EvaluationScorer` | AUTHORITATIVE / REUSE | 保留规则评分与现有维度分数 |
| `SuiteReport` / `reporting.py` | AUTHORITATIVE / REUSE | 保留 JSON/Markdown 报告和 reproducibility metadata |
| planner shadow、skill evaluation、reflection evaluation、experience evaluation | REUSE / ADAPT | 通过 trace/evidence adapter 接入，不重写各自 evaluator |
| `model-evaluation.yml` | REUSE / FREEZE | 继续隔离 offline/live evidence；不让 paid workflow 成为日常 CI gate |
| benchmark scripts | REUSE / ADAPT | 作为 evidence source，不创建第二 Evaluation Framework |
| Task/Runtime/Model trace | REUSE | 只消费 bounded metadata，不保存 prompt/answer |

## Unified EvaluationRecord

`apps/api/app/evaluation/loop.py` 新增 `EvaluationRecord` 及 `EvaluationRecordAdapter`。它覆盖 evaluation/suite/case/evidence、task family/course/capability、expected/actual bounded outcome、score dimensions、overall score、failure stage/codes、task/run/trace lineage、planner/plan/skill/tool/model/reflection/experience versions、latency/tokens/cost、reproducibility 和 baseline/candidate IDs。

旧 `SuiteReport` 通过 adapter 转换；现有 Runner、Scorer、Task API、Runtime Plan、RAG/Tool Interface 不变。raw prompt、answer、message 和 content 在 adapter 中丢弃。

## F1 结论

现有 Evaluation Framework 是唯一 owner；新增 loop 是其下游 evidence/analysis 层，不是第二套执行框架。F1 完成。
