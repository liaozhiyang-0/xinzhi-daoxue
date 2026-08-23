# T3：Targeted 专项测试集建设

## 目标
针对 T2 Top Failure Patterns 建立专项测试集。

## 每个专项规模
20–50 cases；Top 5 合计约 100–200 cases。

## 示例
vision_circuit、phasor_analysis、formula_parsing、long_derivation、rag_grounding、skill_selection、reflection_false_positive、insufficient_information。

## 每个 Suite
包含 positive / negative / boundary / already-correct cases。

每个专项建议保留 20–30% hidden targeted regression cases。

## 输出
- `evaluation/targeted/`
- `docs/testing/t3_targeted_suites.md`

## 提交
`test(eval): build targeted failure suites`
