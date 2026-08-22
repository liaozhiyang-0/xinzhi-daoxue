# Phase J：Robustness / Stress / Regression 审计

## 1. 结论

本阶段完成了 provider-free 的鲁棒性、故障注入、运行时恢复、有限并发和回归验证。未调用付费 Provider，未调整评分阈值，未删除测试，未关闭 workflow，也未修改 Runtime/API 业务实现。

当前结论：`CONDITIONAL GO`。

原因是本地故障矩阵和 1/5/10/20 并发探针通过，但以下证据仍受环境或现有工作树影响：

- 真实 Provider 的 429/500/不可用全链路没有在无预算条件下执行；
- blurred image 没有独立的真实端到端样本；
- CPU/内存没有采样工具，报告明确保留为 `null`；
- `run_e2e_soak.py` 一轮观察到合法 `waiting_review` 和已冻结 data-analysis 失败，不能把它们伪装成 completed；
- Phase H 全量回归保留其 provider-free/缓存条件，结果必须与原 H 基线按同一 fingerprint 解读。

## 2. 证据边界

| 证据层 | 本阶段状态 | 说明 |
| --- | --- | --- |
| 本地单元/契约 | PASS | 故障注入、fail-closed、恢复、SSE、Planner/Skill/Reflection/Experience |
| provider-free API | PASS / 观察项 | 本地 Runtime 服务健康，有限并发无失败 |
| synthetic evaluation | PASS / PARTIAL | 沿用 Phase H/G 的 synthetic provenance 与 cache，不等同真实模型质量 |
| 真实 Provider | CONDITIONAL | 无本阶段新增预算，不执行真实付费调用 |
| 长时 30–60 分钟 soak | NOT CLAIMED | 仅执行一轮约 95 秒有界 soak；不虚构长期稳定性 |

## 3. 测试矩阵

以下命令均从仓库根目录执行，解释器为 `.venv\Scripts\python.exe`。

| 范围 | 命令/脚本 | 实际结果 |
| --- | --- | --- |
| Provider/RAG/Tool | `pytest -q`：model routing/providers/Spark/academic retrieval/multimodal RAG/knowledge QA/external research/professional tools | **83 passed**, 2 warnings |
| Runtime/SSE | controls/checkpoint/parallel recovery/replay/task retry/cancel/idempotency/queue/executor/non-blocking/SSE/event/task execution | **97 passed, 8 skipped**, 2 warnings |
| Planner/Skill/Reflection/Experience/Evaluation | planner/skill/reflection/experience/evaluation + retrieval benchmark + Phase I target | **101 passed**, 2 warnings |
| 输入与附件 | file upload/document ingestion/multimodal batch/evaluation attachments/task API/agent input/runtime preparation/goal planner/SSE | **104 passed**, 2 warnings |
| 有界并发 | `scripts/run_phase_j_robustness.py --levels 1,5,10,20 --timeout-seconds 60` | **36/36 completed**, failure rate 0 |
| E2E smoke soak | `scripts/run_e2e_soak.py --once --research-every 0 --poll-timeout-seconds 60` | 11 cases；9 completed，1 waiting_review，1 failed（冻结 data-analysis）；surface health 200 |

前四组存在测试重叠，不能简单相加为独立 case 总数。

## 4. 输入鲁棒性审计

| 输入类型 | 现有证据 | 结果/边界 |
| --- | --- | --- |
| 空输入/空上传 | `test_file_upload_rejects_empty_and_mismatched_type` | PASS，HTTP 422 |
| 信息不足/低证据 | knowledge QA verification/runtime persistence tests | PASS，fail-closed 或进入 review，不强行成功 |
| 超长、中文/英文混合、公式密集 | agent input mapping、context assembly、evaluation case/公式格式化测试 | PASS；上下文截断会显式 warning |
| PDF | document ingestion blank-page/low-text/OCR follow-up tests | PASS，OCR required/review 状态显式保留 |
| 单图/多附件 | image attachment task flow、evaluation attachment manifest、multimodal RAG tests | PASS |
| 模糊图片 | 质量/降级协议有覆盖 | **缺独立真实 blurred-image fixture**，保留为后续数据缺口 |
| unsupported file/MIME | upload MIME/signature、evaluation attachment extension tests | PASS，拒绝或进入明确 validation error |

## 5. Provider 故障矩阵

| 故障 | 证据 | 结论 |
| --- | --- | --- |
| timeout | `test_interactive_route_does_not_retry_or_wait_for_fallback_on_timeout` | PASS；route-level retry budget 生效，不额外等待 fallback |
| slow response/total timeout | Spark stream timeout tests | PASS；超时可观察 |
| invalid/schema violation | Spark JSON local validation/truncation/usage redaction tests | PASS；不泄露原始无效输出 |
| unavailable/unconfigured | model preflight and provider factory tests | PASS；调用前可判定不可用 |
| 429 | academic retrieval retry-after/cooldown tests | PASS，但这是 retrieval provider 层；LLM 429 全链路未执行 |
| 500 | provider abstraction 有错误边界，未在本阶段执行真实 LLM 500 | CONDITIONAL |
| fallback/retry/budget/terminal state | model route + generic goal fallback + task executor reliability | PASS（synthetic/local）；真实 Provider 结果未宣称 |

## 6. RAG 故障矩阵

已覆盖 empty/insufficient evidence、low confidence、wrong-course/content-type filtering、embedding model failure、optional reranker failure、index/vector degradation、citation validation 和 revoked material。关键断言是：`rag_status=degraded`、`embedding_status=failed`、warning/needs-review 可观察，不能静默用 hash fallback 或伪造强证据。

## 7. Tool 故障矩阵

calculator 的非法表达式会抛出 `ValueError`；generic goal runtime 覆盖 primary unavailable → policy-checked fallback、approval pause/resume、未注册 capability fail-closed 和 invalid parallelism 拒绝。没有测试允许把异常工具结果直接写成成功答案；calculation timeout/malformed/dependency-unavailable 的独立端到端 fixture 仍是后续缺口。

## 8. Runtime 与协议

已通过 resume、retry、cancel、checkpoint、duplicate/idempotency、worker restart recovery、interrupted safe replay、queue dead-letter、SSE reconnect/order/contiguous sequence、non-blocking task creation。已验证恢复不会重复预算扣费或重复 queued event，stale state version 会被拒绝且不污染 control data。

## 9. 并发结果

结果来自 `evaluation/reports/phase_j/concurrency.json`，请求是固定本地问题，provider-free，最大并发 20，无无限压力。

| 并发 | 成功/请求 | failure rate | p50 | p95/p99 | queue p95 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1/1 | 0 | 780 ms | 780 / 780 ms | 139 ms |
| 5 | 5/5 | 0 | 1,872 ms | 1,953 / 1,953 ms | 346 ms |
| 10 | 10/10 | 0 | 5,655 ms | 6,380 / 6,380 ms | 4,677 ms |
| 20 | 20/20 | 0 | 18,872 ms | 23,242 / 23,242 ms | 19,374 ms |

CPU/内存字段为 `null`，原因是当前 `.venv` 没有 `psutil`，没有使用不可靠的估算替代真实采样。

## 10. E2E soak 观察项

第一轮运行曾因 `run_e2e_soak.py` 只把 completed/failed/cancelled 视为终态而长轮询；已对测试脚本作最小修正，将 `waiting_review`、`waiting_user`、`waiting_input` 纳入合法终态。修正后的单轮 smoke 仍观察到：

- `academic_writing` 进入 `waiting_review`，这是人工复核状态，不是 worker hang；
- `data_analysis` 返回 failed，原因是该能力当前冻结，不能将其计为质量通过；
- health、workspace、两个 debug asset HTTP status 均为 200，但现有 asset version 检查返回 `frontend_build_ready=false`，属于现有前端版本串观察项；
- 本阶段没有把这一轮当作全量成功，也没有修改业务代码去迎合 soak。

30–60 分钟长期 soak 没有完成，因此不输出 memory leak/queue growth/stale lock 的通过结论。

## 11. 回归与门禁

- Phase H benchmark：已启动 `python scripts/run_phase_h_benchmark.py`，但当前工作树 fingerprint 变化导致大量 cache miss，进程进入本地视觉/模型失败与长尾路径后被有界中止（exit 1 / Ctrl-C）。因此本阶段不生成新的 H PASS 数字；可复核的 H 结果仍是此前已完成并提交的 provider-free baseline，不能与本次未完成尝试混报。
- Phase I targeted cases：`test_phase_i_ae_bias.py` 已在回归组中通过，BJT/MOS target replay 均保持通过。
- Planner/Skill/Reflection/Experience/Runtime/SSE/API：均已包含在上述回归组并通过。
- 不修改 public API、数据库 migration、Provider budget、评分标准或生产配置。

## 12. Phase J 后续建议

1. 补齐独立 blurred-image、LLM 429/500 和工具 timeout/malformed/dependency fixtures。
2. 在 CI 或受控 runner 安装资源采样依赖后，重复 1/5/10/20 并发并记录 CPU/内存峰值。
3. 修正 `run_e2e_soak.py` 的 `frontend_build_ready` 版本来源，使它读取同一构建版本，而不是放宽断言。
4. 在明确预算和 secret 后，再进行真实 Provider 小样本，不把本地/缓存证据升级为真实质量结论。
