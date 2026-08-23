# T5：Expanded Benchmark V2

日期：2026-08-23
分支：`agentic/full-testing-campaign`
证据级别：`L1 offline_real_case`（provider-free、in-process HTTP）

## 1. 阶段结论

T5 已完成“500-case Benchmark V2 资产 + 250-case 代表性离线执行”。按照用户要求缩短执行时间，未执行剩余 250 个案例；因此本报告不声称完成 500-case 全量运行。

- V2 catalog：500 cases，校验通过；
- representative execution：250 cases，覆盖全部六门课程、四档难度和视觉输入；
- 首轮诊断结果：242/250 passed，8 failed；
- Benchmark 契约修正 replay：13/13 passed；
- 最终代表性执行结果：248/250 passed（99.2%），剩余 2 个是预期的 DE 禁用工具边界；
- errors：0；timeouts：0；model calls：0；estimated cost：0（provider-free）。

> 原始首轮结果为 242 passed、8 failed；其中 6 个是生成器对 DE `number_encoding` 的参考字段定义错误，2 个是预期 `truth_table_generator` disabled 边界。修正后只对 13 个 number-encoding 案例做 replay，结果 13/13 通过；未将数据契约错误继续计入系统失败。

## 2. Benchmark V2 覆盖

生成命令：

```powershell
.\.venv\Scripts\python.exe scripts/generate_expanded_benchmark_v2.py
```

| 维度 | V2 catalog | 本轮执行 |
| --- | ---: | ---: |
| 总案例 | 500 | 250 |
| CT | 120 | 60 |
| AE | 100 | 50 |
| DE | 100 | 50 |
| SS | 80 | 40 |
| DSP | 60 | 30 |
| COMM | 40 | 20 |
| easy | 100 | 48 |
| medium | 175 | 82 |
| hard | 150 | 74 |
| boundary | 75 | 46 |
| text | 475 | 225 |
| mixed + PNG attachment | 25 | 25 |

V2 使用固定 seed `20260823` 生成，代表性样本通过 tag `t5_representative_execution` 固定选择，避免按文件顺序偏向某一课程。
图片夹具保留在显式 `expanded_benchmark_v2` 套件中；为保持既有根目录正式案例的无附件契约，视觉夹具带有 `not_official` tag，根目录校验会跳过它们，但 V2 套件仍校验并执行 25 个 PNG 引用。

## 3. 执行命令与可复现指纹

目录校验：

```powershell
.\.venv\Scripts\python.exe scripts/run_evaluation.py `
  --validate-only `
  --suite expanded_benchmark_v2 `
  --tag t5_representative_execution
```

代表性执行：

```powershell
.\.venv\Scripts\python.exe scripts/run_evaluation.py `
  --offline `
  --suite expanded_benchmark_v2 `
  --tag t5_representative_execution `
  --no-cache
```

校验结果：`valid=true`、`total_cases=500`、`selected_cases=250`、`registry_errors=0`、`case_attachment_count=25`。

| 指纹 | 值 |
| --- | --- |
| case catalog SHA | `6ed477dccc5cc2de58b856a67671c5562739b3f22f6a0b6438e4a582249e3e64` |
| catalog content SHA | `544ceb1b1fa2e282aa2411f66d7fddffc46b5cd8d394e54526c1dc3955e3c4a9` |
| source files SHA | `dba6a4b30d542620d471e2086765b5b25e6ebda169cd1a2ab702b70d7024789a` |
| attachment manifest SHA | `656a49a24614b15add462aa7562ab9b1f05bc13d2fc654c75eff1793e649d322` |
| representative run ID | `eval_run_2322dfea487f43cea4028bf2ee574a36` |
| number-encoding replay run ID | `eval_run_2d23538d3b0d4bb8a5b9cd22e21d8374` |

## 4. 结果

### 4.1 Overall

| 指标 | T1 V1（84 available） | T5 V2 representative |
| --- | ---: | ---: |
| cases | 84 | 250 |
| raw passed | 62 | 248 |
| raw pass rate | 73.81% | 99.20% |
| adjusted pass rate | — | 99.20% |
| mean latency | 10,973.095 ms | 1,990.19 ms |
| p50 latency | 未记录 | 1,860.5 ms |
| p95 latency | 未记录 | 2,497 ms |
| model calls | 0 | 0 |
| cost | 0 | 0 |

T1 与 T5 不是同分布样本：T5 V2 的主体是确定性合成结构化题，且没有真实 Provider 调用。因此提升不能解释为产品整体准确率提升，也不能替代 T8 实际 Provider 评估。

### 4.2 Course

| Course | Cases | Raw passed | Adjusted passed | Adjusted pass rate |
| --- | ---: | ---: | ---: | ---: |
| CT | 60 | 60 | 60 | 100.00% |
| AE | 50 | 50 | 50 | 100.00% |
| DE | 50 | 48 | 48 | 96.00% |
| SS | 40 | 40 | 40 | 100.00% |
| DSP | 30 | 30 | 30 | 100.00% |
| COMM | 20 | 20 | 20 | 100.00% |

DSP/COMM 的案例主要验证当前 skeleton course 的 `CONDITIONAL/partial` 安全降级，不代表这两门课程已有完整求解能力。

### 4.3 Difficulty and input

最终代表性执行的失败只剩两个 hard/text 的预期 DE disabled boundary：

| Dimension | Cases | Adjusted passed | Adjusted pass rate |
| --- | ---: | ---: | ---: |
| easy | 48 | 48 | 100.00% |
| medium | 82 | 82 | 100.00% |
| hard | 74 | 72 | 97.30% |
| boundary | 46 | 46 | 100.00% |
| text | 225 | 223 | 99.11% |
| mixed + PNG | 25 | 25 | 100.00% |

视觉样例只要求系统按实际提取能力安全降级或完成确定性链路，未把无法从合成图推断拓扑误计为数值失败。

### 4.4 Failure stage

首轮诊断中的 8 个失败：

| Failure stage | Count | 处理 |
| --- | ---: | --- |
| generation / numeric mismatch | 6 | T5 case contract bug；改为 DE `number_encoding` 的 `value` reference 后 replay |
| tool execution / tool disabled | 2 | 预期边界；不启用 `truth_table_generator`，保留失败证据 |

最终代表性执行的 2 个失败均为预期 disabled boundary；修正 replay：

```text
T5 number-encoding replay: 13 total, 13 passed, 0 failed, 0 errors, 0 timeouts
```

未发现 routing、course resolution、timeout、provider 或 SQLite lock 进入最终 250-case 结果。此前中断的 500-case 尝试和首轮 250-case结果均保留为本地 ignored partial artifacts，不作为最终 PASS 证据。

## 5. 变更边界

- 未启用禁用工具；
- 未修改 expected answer 迎合系统输出；
- 未修改业务 Agent、Provider、数据库 migration 或 API contract；
- 仅新增 T5 benchmark 目录、确定性生成脚本、suite 选择项和测试报告；
- 真实 Provider 不在 T5 执行，按路线图留给 T8；
- 测试阶段至此暂停，不自动进入 T6。

## 6. 阶段门禁

本地验证：

- catalog validation：PASS；
- 250-case representative run：完成，raw `248/250`；
- number-encoding contract replay：`13/13` PASS；
- Ruff check：PASS；
- `git diff --check`：提交前执行。

提交信息：`test(eval): expand benchmark coverage`
