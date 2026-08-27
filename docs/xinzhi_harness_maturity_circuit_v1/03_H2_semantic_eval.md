# H2：Semantic Eval Harness

目标：解决“后端通过但答案质量差”。

必须扩展现有 evaluation，不得另建第二套评测系统。

EvaluationCase 建议支持：
- case_id
- input
- attachments
- expected_answer
- expected_unit
- key_points
- repeat_count
- expected_artifact
- rubric

第一批 Evaluator：
- NumericEvaluator
- UnitEvaluator
- KeyPointEvaluator
- InstructionFollowingEvaluator
- ImageCoverageEvaluator
- StabilityEvaluator

等级：
A 正确完整
B 核心正确
C 部分可用
D 错误/拒答/空答案

同题重复 3~5 次，统计 route_consistency、answer_consistency、numeric_consistency、review_consistency。

为 Circuit 预留：
`expected_artifact_type = circuit_svg`

真实题库优先，尤其 CT/AE/DE/SS 现成题和电路图。

Semantic Eval 不运行时，不影响生产 Runtime。

提交：
`feat(eval): add semantic quality evaluators`

输出：
`docs/audit/48_semantic_eval_report.md`
