# Phase H：大规模 Benchmark Campaign

## 结论

Phase H 已运行当前工作树中全部 84 个正式 evaluation cases，并生成了按课程、任务、问题类型、输入模式、Agent 能力和难度的汇总，以及 Top-20 failure patterns。路线图要求的 336-case 数据集在当前工作树不可用；因此本阶段证据状态为 `PARTIAL / CONDITIONAL`，不是 336-case 完成声明。

本次仍是 `synthetic_provider_free`：84 个案例的 provenance 全部为 synthetic，未发起外部 Provider 请求。

## 覆盖与总体结果

| 指标 | 值 |
| --- | ---: |
| 当前正式案例 | 84 |
| 本次执行 | 84 |
| 路线图目标 | 336 |
| 当前缺口 | 252 |
| 扩展 500–800 cases | 0 |
| passed | 60 |
| failed | 18 |
| error | 2 |
| timeout | 4 |
| pass rate | 0.714286 |
| mean score | 85.713929 |
| mean latency | 11,395.226 ms |
| max latency | 240,002 ms |

### 按课程

| 课程 | Cases | Pass rate | Mean score | Mean latency |
| --- | ---: | ---: | ---: | ---: |
| AE | 11 | 0.636364 | 90.909091 | 3,955.909 ms |
| CT | 52 | 0.769231 | 85.439423 | 16,552.500 ms |
| DE | 12 | 0.416667 | 74.998333 | 3,319.167 ms |
| SS | 9 | 0.888889 | 95.237778 | 1,458.222 ms |

### 按难度与输入

- `hard`: 6 cases，pass rate 0.166667，mean score 40.475000；这是当前最明显的质量弱项，但样本很小。
- `medium`: 56 cases，pass rate 0.750000，mean score 87.755000；最长尾延迟来自该组。
- `easy`: 15 cases，pass rate 0.733333；`boundary`: 7 cases，pass rate 0.857143。
- `text`: 82 cases，pass rate 0.731707；`mixed`: 2 cases，pass rate 0。当前没有足够图片样本，不能推断图像能力。

## Top Failure Patterns

| Pattern | Count | Stage | 课程/任务 | 处理判断 |
| --- | ---: | --- | --- | --- |
| P01 | 3 | tool_execution / `tool_disabled` | DE / academic solving | 三个案例显式带 `disabled_tool` 标签；记录为已知能力缺口，暂不以特例修复 |
| P02 | 2 | generation / `step_missing` | AE / academic solving | 候选 Phase I 目标，需先用 targeted replay 确认是否是 solver 生成问题 |
| P03 | 2 | timeout | CT / assignment review | 候选稳定性问题；需区分 provider-free fixture 与业务 timeout |
| P04 | 2 | timeout | CT / lesson prep | 候选稳定性问题；需区分 provider-free fixture 与业务 timeout |
| P05 | 2 | unknown / `execution_error` | DE / data analysis | 当前证据不足，先不归因 |
| P06–P18 | 1 each | citation/routing/verification/generation | 多课程 | 单例，保持观察，不为单题写特例 |

P01 的三个案例是 benchmark 中主动标记为 `disabled_tool` 的负向能力边界；不能把“工具未启用”误判为随机回归。P03/P04 的 timeout 需要保留作为 J 阶段故障/长尾输入，而不是通过增加 timeout 掩盖。

## 输出

本地忽略目录保存了完整机器可读结果：

- `evaluation/reports/phase_h/latest.json`
- `evaluation/reports/phase_h/summary.json`

机器可读 summary 包含 `per_course`、`per_task`、`per_problem_type`、`per_input_mode`、`per_agent_capability`、`per_difficulty`、Top-20 patterns 和 latency bottlenecks。

## 可复现命令

```powershell
.venv\Scripts\python.exe scripts\run_evaluation.py --validate-only
.venv\Scripts\python.exe scripts\run_phase_h_benchmark.py
```

该 harness 复用现有 `EvaluationCaseLoader`、`EvaluationRunner`、scorer 和 G 的 provider-free cache；不修改评分器、测试答案、Agent、Planner 或 Runtime。若拿到授权的 336-case/expanded catalog，应在独立数据版本下重跑并替换本报告的 coverage 结论。
