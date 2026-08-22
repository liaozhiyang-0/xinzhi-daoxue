# Phase I：Failure-driven Targeted Optimization

## 结论

Phase I 只处理 H 的可复现 P02：AE `bjt_bias` / `mos_bias` 在缺少数值条件时没有暴露“工作区判断”这一已有 course verification rule，导致两个案例都在 `generation / step_missing` 失败。

采用一个最小的 course-pack 级修复：`BaseCoursePack.required_solution_steps()` 在存在 `operating_region` 规则且题型为 BJT/MOS bias 时，输出一个 `course_verification / operating_region / 工作区判断 / pending` 步骤。该步骤表达“需要继续判断”，不会编造工作区结论，也不调用 Provider。

没有处理 H 的 P01：它来自 3 个显式带 `disabled_tool` 标签的 DE 负向 fixture，属于已声明能力边界；没有为单题增加特例。H 的 timeout、unknown 和单例 pattern 也未通过提高 timeout 或修改 scorer 掩盖。

## Proposal → Replay → Regression

| 项目 | 结果 |
| --- | --- |
| Pattern | P02 `generation + step_missing`, AE, 2 cases |
| Root-cause evidence | 两例实际输出均只有通用 no-deterministic-equation 文本；AE pack 已有 `operating_region` rule；required step 为“工作区” |
| Minimal change | course-pack step contract + graph composition；无新 Agent、无 Runtime/Planner 重写 |
| Target cases | `AE_BJT_001`, `AE_MOS_001` |
| Before | 2/2 failed，score 71.43，failure stage `generation` |
| After | 2/2 passed，score 100.0，failure stage none |
| Score delta | +28.57 each |
| Cost delta | 0；provider-free，external calls 0 |
| Regression | 0 in targeted regression matrix |

串行 replay 的原始 JSON 保存在本地忽略目录 `evaluation/reports/phase_i/`。两个 case 的 after latency 分别为 29,411 ms 与 29,595 ms；该结果是 offline runtime latency，不是 Provider latency。最初并行启动两个 replay 造成共享 SQLite evaluation DB lock，随后串行重跑成功；并行干扰未计入质量结果。

## 回归门禁

```text
134 passed, 2 warnings
```

覆盖：

- `test_targeted_solver_optimization.py`
- `test_universal_academic_solver.py`
- `test_academic_solver_runtime.py`
- `test_evaluation_framework.py`
- `test_real_evaluation_framework.py`
- `test_evaluation_loop.py`
- `test_retrieval_benchmark.py`

同时通过：

- changed-file Ruff
- changed-file Mypy（ignore-missing-imports / follow-imports=skip）
- 目标案例 offline replay

## 轮次控制

- Round 1：完成 P02 最小修复并通过 target replay。
- Round 2：未启动；没有证据支持扩大修改范围。
- Round 3：未启动。

## 边界

本阶段没有修改评分器、答案、测试阈值、Provider 配置、数据库 schema、API contract、Planner、Skill Registry 或 Runtime。真实 Provider 证据仍缺失，H 的 84/336 数据集缺口也仍然存在。
