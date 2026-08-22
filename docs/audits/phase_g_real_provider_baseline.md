# Phase G：真实 Provider Baseline 与 Benchmark Harness

## 结论

Phase G 完成了受控的 L0 provider-free baseline，并完成了一个受限的 L1 本地教材检索 benchmark。当前不能宣称真实模型质量基线：正式 `evaluation/cases` 的 84 个可用案例全部标记为 `synthetic`，本机没有可用 Provider key，也没有用户授权的付费预算。因此 L2 real-provider test 按路线图安全跳过。

证据状态：`CONDITIONAL`。

## 执行范围

| 层级 | 数据 | 数量 | 结果 | 证据边界 |
| --- | --- | ---: | --- | --- |
| L0 `synthetic_provider_free` | 现有正式 evaluation cases 的分层代表集 | 40 / 84 | 25 passed, 12 failed, 1 error, 2 timeout；pass rate 0.625 | 可验证执行链和回归行为，不能代表真实模型质量 |
| L1 `offline_real_case` | 本地教材检索草案 | 15 | Recall@1 0.800000；Recall@3/5 0.866667；MRR 0.822222 | `review_status=draft`，不是正式官方 benchmark |
| L2 `real_provider_test` | 无 API key / 无明确预算 | 0 | SKIP | 没有外部模型请求 |

L0 的 40 个案例由 `run_phase_g_baseline.py` 按课程、任务族、输入模式先取每组代表，再按稳定 case id 补齐。当前 84 个正式案例的 provenance 全部为 `synthetic`，覆盖 CT、AE、DE、SS；正式目录没有 DSP 案例。

## L0 基线摘要

| 指标 | 值 |
| --- | ---: |
| selected cases | 40 |
| available official cases | 84 |
| mean score | 80.356750 |
| pass rate | 0.625000 |
| p50 latency | 1,419 ms |
| max latency | 180,005 ms |
| known cost | 否；offline provider-free |

Failure stages：`generation` 5、`routing` 3、`citation_validation` 2、`timeout` 2、`course_pack_resolution` 1、`verification` 1、`unknown` 1。上述统计保留现有 runner 的评分和 timeout 标准，没有修改 scorer、测试答案或业务配置。

课程分布如下：AE 11 cases / pass rate 0.636364，CT 23 / 0.652174，DE 3 / 0.333333，SS 3 / 0.666667。该分层样本不覆盖 DSP，不能据此推断 DSP 质量。

## L1 检索证据

15 个案例来自 `evaluation/knowledge_retrieval/cases`，其状态仍是 `draft`。`local_lexical_v2` 的结果保存于本地忽略目录 `evaluation/reports/phase_g/knowledge_retrieval_l1.json`；它只证明本地 corpus/retrieval 路径可运行，不等价于生成模型的 grounded answer 质量。

## Real Provider 门禁

- `.env` 文件存在，但本次检查的 Provider key 均未配置。
- 未自动修改 key、secret、model alias 或预算。
- 未调用付费 Provider，成本为 0（而非未知的真实调用成本）。
- 按路线图要求，真实 Provider subset 留待具备明确 key、`max_cases`、`max_model_calls`、`max_tokens`、`max_estimated_cost` 和 timeout 后执行。

## 可复现命令

```powershell
.venv\Scripts\python.exe scripts\run_evaluation.py --validate-only
.venv\Scripts\python.exe scripts\run_phase_g_baseline.py --max-cases 40 --no-cache
.venv\Scripts\python.exe evaluation\knowledge_retrieval\scripts\run_retrieval_benchmark.py --mode local_lexical_v2 --output evaluation\reports\phase_g\knowledge_retrieval_l1.json
```

输出：

- `evaluation/baselines/agentic_v1_real_baseline.json`
- `evaluation/reports/phase_g/latest.json`（本地生成，按仓库规则忽略）
- `evaluation/reports/phase_g/knowledge_retrieval_l1.json`（本地生成，按仓库规则忽略）

## Phase G 边界

本阶段没有根据结果修改 Agent、Planner、Runtime、RAG、Tool 或评分器，也没有将 synthetic 结果写成 real-provider 结论。下一阶段只能将这份 baseline 作为受限回归输入，并先完成 H 的全量/扩展 benchmark 覆盖和失败聚类。
