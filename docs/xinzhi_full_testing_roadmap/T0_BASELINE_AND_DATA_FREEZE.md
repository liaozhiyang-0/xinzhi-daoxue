# T0：测试环境与数据基线冻结

## 目标
保证后续所有测试结果可比较。

## 必须冻结
记录 git commit SHA、planner/skill/prompt/rag/tool/reflection/experience/evaluation version、provider/model version。

## 测试数据
确认现有 336-case suite。每个 case 至少有：
case_id、course、task_type、problem_type、difficulty、input_mode、expected_answer/rubric、source。

缺字段可补 metadata，不修改原题和答案。

## 历史失败基线
已有 pre-existing test failures 单独记录为 `known_baseline_failures.yaml`。

## 输出
- `evaluation/baselines/current_system_manifest.json`
- `docs/testing/t0_baseline_freeze.md`

## 提交
`test(eval): freeze benchmark baseline`
