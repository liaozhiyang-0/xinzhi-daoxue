# T4 定向优化 Replay / Counterfactual Test

日期：2026-08-23
分支：`agentic/full-testing-campaign`

## 范围与约束

本轮只处理 T2 已归因、且属于 Academic Solver 确定性链路的三个数值缺口：

- P09：AE 理想反相运放自然语言数值未结构化；
- P10：CT 功率自然语言数值未结构化；
- P08：DE 二进制转换自然语言数值未结构化。

未启用 `boolean_simplifier`、`truth_table_generator`、`hdl_static_analyzer` 等禁用工具，未修改 API、数据库、Provider 配置或评估标准。

## Replay 记录

| Proposal | Target pattern | Files changed | Baseline | Candidate | Delta | New failures | Latency / cost |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| T4-R1 | P09 + P10：显式电阻、电压、电流文本转结构化方程 | `academic_solver_graph.py`、`test_t4_numeric_parser.py` | AE 57.14；CT 57.14；均 fresh uncached 0/1 | AE 100；CT 100；均 fresh uncached 1/1 | +42.86 / case | 0 | 候选约 30.3s / case；0 model call；成本 0。历史基线为缓存报告约 1.9s，不能与 uncached 启动耗时直接比较 |
| T4-R2 | P08：显式二进制文本转十进制标量结果 | 同上 | 57.14；fresh uncached 0/1 | 100；fresh uncached 1/1 | +42.86 | 0 | 0 model call；成本 0。首次候选已发现并修复 `value` 列表包装和关键词缺失两项契约问题 |

实现保持窄范围：

1. 仅当题目没有既有方程和目标量时触发显式模式识别；
2. AE/CT 只接受单位和关系完整的标量形式；
3. DE 只接受 `二进制` 与 `十进制/转换` 同时出现的显式形式；
4. DE 单值结果在结果边界解包为标量，避免通用工具列表包装遮蔽评估目标；
5. 其他题型和已有结构化输入保持原路径。

## 局部回归

命令：

```powershell
.\.venv\Scripts\python.exe -m pytest `
  apps/api/tests/test_t4_numeric_parser.py `
  apps/api/tests/test_universal_academic_solver.py `
  apps/api/tests/test_evaluation_framework.py `
  apps/api/tests/test_evaluation_loop.py -q
```

结果：`100 passed`，仅有既有依赖弃用告警。

静态检查：

- Ruff check：PASS；
- Ruff format check：PASS；
- Mypy（目标代码与新增测试）：PASS；
- `git diff --check`：提交门禁执行。

## 官方 Academic Solver 回归

命令：

```powershell
.\.venv\Scripts\python.exe scripts/run_evaluation.py --offline --suite academic_solver --no-cache
```

结果：26 cases，22 passed，4 failed，0 errors，0 timeouts，pass rate 84.62%。4 个失败均为既有 `tool_disabled` 断言：

- `DE_BOOLEAN_001` → `boolean_simplifier` disabled；
- `DE_TRUTH_TABLE_001` → `truth_table_generator` disabled；
- `DE_STATE_001` → `truth_table_generator` disabled；
- `DE_VERILOG_001` → `hdl_static_analyzer` disabled。

它们与本轮修改无关，且不能通过启用工具“修复”。

曾启动 84-case uncached 全量离线回归，但知识问答案例在未配置模型的 offline settings 下仍按 180 秒 Provider 超时预算串行等待；该命令已停止，未将中断结果计入 PASS。既有 T1 84-case baseline 作为未修改域对照保留。

## 真实 Provider 受控样本

用户已确认模型余量可用。本轮使用 `--live --confirm-paid --no-cache` 运行 T2 重点样本；DashScope `qwen3.5-flash` 成功完成 teaching/assessment 生成，未发生 Provider 配置错误。

| Case | Provider 结果 | 评估结果 | 归因 |
| --- | --- | --- | --- |
| `COMMERCIAL_FACULTY_001` | 1514 tokens，completed | failed，28.57 | route / teaching contract mismatch |
| `COMMERCIAL_ASSESS_001` | 903 tokens，completed | failed，28.57 | route / teaching contract mismatch |
| `CONTEST_TEACH_001` | 2293 tokens，completed | failed，28.57 | route / teaching contract mismatch |
| `CONTEST_ASSESS_001` | 2038 tokens，completed | failed，28.57 | route / teaching contract mismatch |
| `COMMERCIAL_DATA_001` | 未调用模型 | error，HTTP 409 | task creation conflict |
| `CONTEST_RESEARCH_001` | 未调用模型 | error，HTTP 409 | task creation conflict |

真实样本用于验证 Provider 链路和失败归因，不把当前 teaching/task-creation 缺口误归因到 T4 数值解析改动；本轮不修复这些跨域问题。

## T4 结论

- 目标改善：PASS，三个目标案例均达到 100 分；
- critical regression：0；
- 全局退化：未发现与本轮文件相关的新失败；Academic Solver 仅保留既有禁用工具边界失败；
- latency：本轮为 uncached in-process HTTP，启动与知识索引初始化占主要耗时，未发现模型调用或成本增加；
- real model：链路可用，但 T2 的 route/teaching 与 task-creation 缺口仍需后续阶段处理。

T4 仅包含上述定向最小修复；完成本地测试、diff 检查、提交、推送、CI 和 remote SHA 验证后结束，不自动进入 T5。
