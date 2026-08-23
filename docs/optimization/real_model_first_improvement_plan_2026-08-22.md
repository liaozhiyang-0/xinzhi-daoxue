# 芯智导学真实模型优先改进任务单

> 版本：v1.0；日期：2026-08-22
> 来源：组员一、组员二 31 个场景长期改造台账，以及《学科智能体项目功能与架构审计报告》。
> 目标：把“代码契约通过 / Mock Runtime 通过”升级为“真实模型、真实 Agent、真实 Runtime 和 Edge 页面可审计通过”。

## 一、执行原则

1. **真实模型优先**：工作台、展示案例和 31 场景验收默认使用已经发布且配置完整的真实 Agent/Provider；不再把 Mock 结果作为正常业务完成结果。
2. **Mock 仅用于边界测试**：Mock 只允许用于错误注入、超时/取消/断线模拟、结构化契约反例、无 Provider 环境下的快速单测和安全拒答测试；必须显式标记 `mock_used=true`，不得进入真实验收统计。
3. **模型健康不等于任务可用**：任务执行前必须同时验证 Provider、Agent 发布状态、Flow ID、模型模态、RAG、外部检索和输出能力，并将能力快照写入 Runtime。
4. **真实结果必须可追踪**：每次真实回放都关联 `scenario_id → request_id → task_id → runtime_run_id → evidence_id → output_contract_version`，保存 provider、model、flow、耗时、重试、SSE 顺序和终态。
5. **失败优先暴露**：真实模型输出截断、证据不足、RAG 降级、能力缺失、审核未完成和公式不安全时，必须进入明确的待复核/失败/等待状态，不得生成看似完整的答案。
6. **Edge 是最终验收入口**：真实业务场景从 Edge 工作台提交并观察；后端接口和脚本只用于诊断、证据打包和复现，不替代页面验收。
7. **保持冻结基线**：不修改 `apps/api/app/agents/solver_ct`；新的模型、Agent、课程和 Provider 能力通过现有路由、Provider 和环境变量扩展。

## 二、验收等级和禁止事项

> 2026-08-22 追加：Q01 历史任务的数学白名单缺口已处理并完成一次真实复验；但最新 Edge 复验仍暴露真实模型输出中的 `unsupported_command:Big`，因此数学质量仍按 `needs_review` 处理，不能宣称公式质量已完全通过。长期未完成项仍包括 31 场景 T2/T3、剩余图片语义验收、科研证据、备课/科研多轮恢复、治理 Agent、并发/重连和准生产发布门禁。

> 2026-08-22 运行环境追加：发现临时 `docker cp` 注入模型和源码会在 Worker 重建后丢失，导致真实模型 warmup 降级或 Worker 因 lease 保护退出。已将 `HF_MODEL_CACHE_HOST_PATH` 作为 API/Worker 的只读缓存挂载，并重建两类镜像；重建后 Worker 日志为 `task_worker_started`、`rag_model_warmup_completed status=ready failed=[]`，API 健康为文本 512 维、图像 768 维、Qdrant compatible。随后增加 `HF_HUB_OFFLINE=1` 与 `TRANSFORMERS_OFFLINE=1`，消除只读缓存 `.no_exist/processor_config.json` 写入警告；仍需在准生产环境验证缓存版本/权限/挂载路径治理。

> 2026-08-22 Q01 真实复验追加：任务 `task_1bf25313a69340149f54bc26726e9d02` 使用真实上传文件、真实 Redis Worker、DashScope `qwen3.7-plus` 完成；`mock_used=false`、视觉结构 `complete`、真实生成 `completed`、`can_continue=true`，数学质量 `status=passed`、`publishable=true`、无 warnings。此前真实输出逐步暴露的 `\\in`、`\\Rightarrow`、`\\implies`、`\\cap` 白名单缺口均已补齐。整体质量门仍为 `partial`，因为模型解答尚未由完整确定性工具验证；该任务不计 Edge T2。

> 2026-08-22 视觉鲁棒性追加：真实模型曾将同一信号图随机返回为空/不确定结构并错误阻断；已增加窄化的“题干已提供完整信号事实”放行，保留视觉不确定性，电路组件/连接仍拒答。回归测试 `58 passed`，并已在真实任务中验证 `visual_structure_status=complete` 与 `can_continue=true`。

> 2026-08-22 Worker 重启后真实 Runtime 回归：授权开发 E2E `solver_series_current` 生成任务 `task_b586ba73ab854cd48bcf806636f6e104`，24 个事件严格递增，`completed=1`、`timeouts=0`、`agent_mismatches=0`；审计包记录 `mock_used=false`、DashScope `qwen3.6-flash`、模型调用 1 次、Provider latency 8078 ms。结果质量仍为 `partial/needs_review`，因为该简单题未触发独立确定性验证；这证明缓存离线配置未破坏真实模型执行，但不计 Edge T2 或内容零缺口通过。

> 2026-08-22 真实 Showcase Runtime 增量：`general_stack_explanation`（`GENERAL_QUESTION_V1`）与 `knowledge_capacitor_voltage`（`LEARN_01_LOCAL_RETRIEVAL_V1`）均完成，分别产生 23/20 个严格有序事件、无 fallback/timeout；知识问答使用 DashScope，产生 `retrieval_trace_id`，审计包 `mock_used=false`。通用问答的记录仍显示 `local_agent`，未提供独立模型名，因此只计 Runtime/非 Mock 回归，不计真实模型内容零缺口通过。

> 2026-08-22 真实科研写作治理修复：真实 `RESEARCH_02_ACADEMIC_WRITING_V1` 回放发现 `evidence_status=insufficient`、`evidence_count=0` 仍被渲染为 `accepted/publishable`。已在业务输出和确定性治理层补齐 `publishable=false`、`requires_review=true`，引用/事实未核验时强制 `accepted_with_warnings`；容器重建后的任务 `task_348749015f35403a8a815286ebf12e23` 已实测 `validation_status=warning`、`result_status=accepted_with_warnings`。新增治理回归并通过。

> 2026-08-22 真实外部检索回归：`RESEARCH_01_ACADEMIC_SEARCH_V1` 任务 `task_5851a791781e4156acaf8c2ce2d6ae3a` 完成，27 个事件严格递增；外部检索节点真实完成，返回 6 条带 arXiv/DOI、URL、provider、摘要和 `evidence_status=approved` 的来源，`review_status=approved`、整体 `evidence_status=sufficient`、`mock_used=false`。结果仍为 `accepted_with_warnings`，场景合同的模型综合发布门为 false，不能仅凭检索返回计为科研内容完全发布通过。

> 2026-08-22 数据分析真实金丝雀：在受控 `DATA_ANALYSIS_ENABLED=true` 下，真实 `RESEARCH_03_DATA_ANALYSIS_V1` 任务 `task_811085d733bf4bcdaa6e0b9ca78e8039` 使用 DashScope `qwen3.5-flash` 完成 24 行 CSV 分析；21 个 Runtime 事件严格递增、无 Mock、无 fallback，`metrics.manual_review_required=true` 与 `business_data.human_review_required=true` 一致。该过程修复了教学增强层覆盖上游人工复核门的问题；金丝雀结束后已恢复默认 `DATA_ANALYSIS_ENABLED=false`。

> 2026-08-22 真实教学/作业回归：`TEACH_01_LESSON_PREP_V1` 任务 `task_9ba6360221a347a08d909b5216f42360` 与 `TEACH_02_ASSIGNMENT_REVIEW_V1` 任务 `task_2c08800f1c7447d9bbe16bc749cbc9ac` 均完成、事件严格递增、`mock_used=false`、模型路由分别为 `qwen3.5-flash`，但业务状态为 `completed_with_gaps`，不能计内容零缺口通过。

## 当前长期执行快照（2026-08-22）

- **RM-P0-01：部分完成。** 应用默认运行身份已切换为 `local`，`ALLOW_MOCK_FALLBACK=false`；健康接口已返回真实模型 Provider 配置快照，Edge `/system` 已区分“真实模型 Provider”和“Agent Runtime”。当前 DashScope 与 Spark 路由均已配置，26 条模型路由无不可用项；但仍需补齐发布状态、Flow ID 与 Runtime 运行记录的逐次对账。
- **Runtime 别名阻断：已修复。** Edge 首次真实知识问答暴露 `LEARN_01_KNOWLEDGE_QA_V1` 没有本地 Runtime handler；已让 `supported_agent_ids` 参与本地 Runtime 注册，并增加回归断言。第二次 Edge 重试已进入终态。
- **真实 Edge 冒烟：链路通过，内容未验收。** 第二次知识问答已真实调用 DashScope（API 日志记录 HTTP 200），页面显示“带提示完成”，但当前课程没有检索到足够资料，答案明确标记资料不足；这只能计为真实链路/拒答质量门观察，不计为知识答案通过。
- **资料不足展示门：已完成。** 无真实模型生成时，Worker 更新并重新通过 Edge 验证后显示“资料不足，待补充”，答案质量明确提示“本次未生成模型答案”，执行过程中的“结果检查”和“回答生成”均为 `partial`；同时修复了 Lesson Runtime 已调用真实模型却因旧字段缺失被误报为“未生成模型答案”的分支，避免把真实模型草稿和检索拒答混为一谈。
- **RM-P0-03：文本与本地视觉向量链路已恢复。** 已用原生 Transformers 加载真实 `BAAI/bge-small-zh-v1.5`（CPU、512 维、归一化向量），并通过 Qdrant 512 维兼容检查；真实 AE 查询返回 5 条教材证据，`rag_status=ready`、`embedding_status=ready`、`vector_store_status=ready`。真实 `google/siglip2-base-patch16-224` 也已在 API/Worker 中加载（CPU、768 维、归一化图像向量），Qdrant 图像集合 `image_visual=768` 兼容，健康状态已恢复 `ready`。
- **本轮真实 RAG 证据：** `POST /api/v1/knowledge/rag-search` 使用 AE 课程和“负反馈放大器稳定性”查询，命中第八章教材片段，记录 `retrieval_trace_id`、来源章节、512 维 dense 检索和 `confidence=0.660572`；该结果证明文本 RAG 链路可用，不等于 31 个场景已通过。
- **RM-P0-02：已完成一次真实恢复验收，仍需多场景扩展。** DashScope `qwen3.5-flash` 的真实课程分类调用在 `max_tokens=16` 下返回 `finish_reason=length`；内部 Agent 自动以 512 token 上限重试，最终返回完整 `course=AE` JSON，并保留 `structured_recovery_attempted=true`、初次 finish reason、累计 usage 和耗时。还需在备课、科研和视觉结构化场景各完成真实连续回放。
- **Edge 短暂阻塞已恢复：** Edge 曾在直接打开 debug 页面时显示 `ERR_BLOCKED_BY_CLIENT`，随后 `/workspace` 恢复可用；已从工作台重新提交真实课程问题并保存页面终态、证据和任务 API 审计记录。
- **Edge 真实知识问答已恢复并完成一次可审计回放。** Edge `/workspace` 提交 AE“负反馈放大器稳定性/自激振荡”问题后，页面显示 `知识问答 · 模拟电子技术`、`带提示完成`、使用 3 条课程资料、Runtime 已完成；任务记录 `provider=dashscope`、`generation_model=qwen3.5-flash`、2 次模型调用、`S1/S2/S3` 和真实教材来源。该回放的 RAG 因 SigLIP 未加载仍为 `degraded`，答案质量为“需要复核”，因此计为真实链路通过，不计为无缺口内容通过。
- **指标错报已修复并完成 Edge 复验。** 上述任务暴露知识问答生成耗时被写成 0 ms；修复后同题 Edge 回放的任务记录为 `provider_latency_ms/model_latency_ms=6549`、`cloud_ms/model_ms=6549`、`model_calls=2`、`provider=dashscope`、`generation_model=qwen3.5-flash`，页面生成耗时不再是 0 ms。该任务仍因 SigLIP 缺失为 `rag=degraded/evidence=partial`，`mock_used=false`。
- **真实 Q01 视觉链路已完成后端与 Edge 通用工作台复验。** 通过 Edge `/workspace` 真实上传组员一 Q01 原图、真实队列/Worker、真实 `ACADEMIC_PROBLEM_SOLVER` 和 DashScope `qwen3.7-plus` 完成任务 `task_e4cf84d8fa914c5a978e7b5997a70962`；`mock_used=false`、`fallback_used=false`、视觉结构 `complete`、模型完成、输出分段式与拐点解释。页面在静态资源刷新后正确显示 `实际 Provider=dashscope`、`Runtime 通道=local_graph`、`生成模型=qwen3.7-plus`。该次仍因 `visual_acceptance=not_configured`、场景证据审查未执行、整体质量 `partial`/数学 `needs_review`，不计 G1-Q01 T2 内容零缺口通过。
- **Provider/模型展示一致性已补齐。** `TaskResultPresentationService` 现在从视觉、生成、验证执行记录同步真实 Provider/模型到持久化展示投影；工作台区分真实生成 Provider 与 Runtime 适配通道，并增加前端静态资源版本号，避免浏览器缓存旧展示合同。定向回归 `7 passed`，真实 Edge 页面已复核。
- **当前不可宣称完成：** 31 场景 T2/T3、剩余 8 个图片语义验收、Q01 专用场景证据/视觉验收合同、真实科研来源逐条审计、备课/科研结构化输出的多轮恢复、独立知识治理 Agent、双 Worker/重连/并发和准生产发布门禁。
- **本轮增量验证：** `test_spark_llm_provider.py` 为 `5 passed`；新增 RAG 维度质量门为 `1 passed`；健康/模型路由/UI 组合为 `5 passed, 39 deselected`；涉及文件 Ruff 通过、Python 编译通过、冻结基线未修改。Mypy 本轮定向命令超时，未计入通过，需在下一轮统一门禁重新执行。

| 等级 | 用途 | 是否可计入场景已验收 |
| --- | --- | --- |
| T0 | 静态检查、确定性规则、契约反例、Mock 故障注入 | 否 |
| T1 | 真实 Provider 单 Agent 冒烟，确认模型、Flow、解析和错误详情 | 否，仅作为环境准入 |
| T2 | Edge 真实任务链路：输入、路由、Runtime、SSE、结果和证据 | 是，需满足场景门槛 |
| T3 | Edge + 双 Worker/共享存储的重试、取消、重连、恢复和治理验收 | 是，作为发布门槛 |

以下结果不得标记为“真实通过”：

- `provider=mock`、`mock_used=true` 或本地后备答案；
- 只有路由、Schema 或最终文本通过，没有 Runtime 和证据关联；
- RAG `degraded` 却未明确显示资料核验不足；
- 科研候选未完成审核，或引用不能回溯到来源；
- 图片仅完成字节上传，未完成视觉结构化字段验收；
- 公式仅出现在结构化 JSON，未进入最终可读正文；
- 任务最终显示成功，但 `publishable=false`、`requires_review=true` 或存在未解释质量缺口。

## 三、P0：先消除“真实模型可用但工作台仍是假执行”的根因

### RM-P0-01 Provider/模型/运行配置统一

**对应审计：** P0-1、P0-4；上一阶段风险 1、9。
**问题：** `/health` 显示 `active_provider=mock`，但实时 Qwen 健康检查可用；源码、`.env`、运行进程和发布预检存在漂移。

**任务：**

- 建立启动时不可变的 `provider/model/flow/config_version/build_version` 快照；
- `/health`、模型健康、路由预检、Runtime 运行记录和 Edge 结果必须显示同一快照；
- 真实模式必须显式授权，不允许开发环境自动从 Mock 静默切换到真实 Provider；
- Mock 模式和真实模式在 UI、日志、审计和验收报表中明确分离；
- 启动发现 `requested_provider`、`active_provider`、发布状态或配置版本不一致时阻止 production-ready。

**验收：** T1 真实模型冒烟能在 Edge/Runtime 详情中看到一致的 Provider、模型和 Flow；配置漂移时任务在创建前明确失败；不提交凭据。

### RM-P0-02 真实模型结构化输出截断与恢复

**对应审计：** P0-2；上一阶段 G1-Q10、G2-02、G2-03、G2-08、G2-12、G2-13。
**问题：** 备课在 1200 tokens 截断，`finish_reason` 未进入错误详情，没有针对截断的恢复策略。

**任务：**

- 按场景复杂度计算输出预算，禁止所有 Agent 共用固定小预算；
- 将 `finish_reason`、输出长度、解析阶段、重试次数写入受限错误详情；
- 对可恢复截断执行一次有边界的结构化续写/压缩重试，保持幂等 execution key；
- 重试仍失败时输出 `provider_output_truncated` 或 `structured_output_invalid`，不得生成空成功结果；
- 前端区分“模型输出截断”“资料检索失败”“模型能力未配置”；
- 对 G1-Q10、G2-02、G2-03、G2-08、G2-12、G2-13 使用真实结果检查课时、公式、来源和结构字段。

**验收：** 真实 Provider 连续运行至少 3 次；成功结果有完整结构，截断结果有明确失败/待复核终态，不能靠 Mock 固定 JSON 通过。

### RM-P0-03 RAG 质量门与业务能力开关

**对应审计：** P0-3；上一阶段风险 4、6。
**问题：** embedding/reranker 未加载时，备课、学习路径、知识治理仍可能被当成已完成的资料型业务。

**任务：**

- 将 `embedding/reranker/vector_store/material_status` 纳入统一 capability matrix；
- 资料型场景在 RAG 降级时只能进入明确的“资料不足/待复核”路径，不能静默当作语义检索成功；
- 课程资料引用必须保留来源、章节、版本和命中方式；
- 对无资料、低相关资料、撤回资料和跨课程资料增加真实结果拒绝门；
- 学习路径和备课结果必须区分“模型建议”与“基于本课程资料的建议”。

**验收：** T1 检查 RAG 真实健康；T2 用 G1-Q10、G1-Q12、G2-02、G2-03、G2-08、G2-12、G2-13 验证 RAG 正常、降级、无资料三种状态，页面和合同一致。

### RM-P0-04 发布预检与 Runtime 单一状态源

**对应审计：** P0-4；上一阶段风险 3、4。
**问题：** 发布预检、场景就绪接口和运行进程对 Agent `publication_status` 的判断可能不一致。

**任务：**

- 以最终 `RouteDecision` 和不可变 capability snapshot 作为 Runtime 唯一输入；
- `local/demo/published/production-ready` 的含义统一到一个版本化合同；
- 未发布 Agent、缺 Flow ID、缺真实模型、RAG 未就绪或检索未就绪不得标记 production-ready；
- 任务恢复时重新核对能力快照，能力变化只能进入明确重规划/失败，不得继续使用旧能力；
- Edge 页面展示真实发布状态和阻断原因。

**验收：** 用一个已发布真实 Agent 和一个未发布 Agent 做成对 Edge 测试；两者的路由、任务创建、终态和 UI 不能混淆。

## 四、P1：统一 Agent 能力，减少 Legacy 和错误复用

### RM-P1-01 Runtime/Legacy 执行路径收敛

**对应审计：** P1-1；上一阶段 Runtime 统一化任务。
**任务：**

- 盘点并标记 `legacy-runtime:*`、`legacy_provider`、`_build_legacy_plan()` 的真实调用者；
- 新真实 Agent 默认只允许 durable Runtime；Legacy 仅保留兼容迁移和明确的回归用例；
- Runtime 事件、失败、取消、重试、审计和证据包不能因分支不同而改变协议；
- 每个 Legacy 分支建立迁移期限和删除条件，禁止继续增加新业务逻辑。

**验收：** G2-04、G2-10、G2-11、G2-16、G2-17 使用真实 Agent 验证相同任务协议、SSE 顺序、取消和失败审计。

### RM-P1-02 知识治理建立独立 Agent 能力

**对应审计：** P1-3；组员一 G1-Q14。
**任务：**

- 新增独立资产治理能力合同，不复用学习路径 Prompt 作为最终能力；
- 固定资产 ID、来源、版本、审批状态、可见范围、授权和发布阻塞字段；
- 增加版本比较、冲突识别、撤回、重新发布和回滚检查协议；
- 由真实 Agent 负责解释，确定性规则负责权限、版本和发布结论；
- 学生私有资产进入公共课程库必须经过人工审批和审计。

**验收：** G1-Q14 在 Edge 中完成“私有→申请→审批→发布→撤回→重新发布”流程；任何越权读取或未审批发布均失败。

### RM-P1-03 真实 Showcase 不再只测路由

**对应审计：** P1-2。
**任务：**

- 六个展示案例全部改为 T1/T2 真实 Provider 验收；
- 测试结构字段、RAG 命中、引用、质量门、错误恢复和最终展示，而非仅检查按钮和 Agent ID；
- 真实结果必须关联输入哈希、运行批次、证据和展示版本；
- 每个案例至少保留成功、证据不足、Provider 截断/超时三类结果。

**验收：** 六案例各至少 3 次真实运行，结果差异、失败原因和人工复核记录可追溯。

## 五、P1：31 个场景真实模型改进批次

### RM-P1-04 组员一图片场景 G1-Q01～G1-Q09

**现状：** 用户已允许 Edge 访问文件 URL；Edge `/workspace` 已成功完成 Q01 原图选择、上传、真实视觉结构化和求解回放，但当前通用工作台未绑定 `visual_acceptance.v1` 专用场景合同，故仍未达到图片场景 T2。
**任务：**

- 解除 Edge 文件 URL 权限后逐题上传原图；
- 每题先由真实视觉 Agent 输出节点、坐标、连接、极性、参考方向、单位和不确定项；
- 通过 `visual_acceptance.v1` 后才能进入求解；
- G1-Q01/Q02/Q03 验证卷积、频谱和带通采样字段；
- G1-Q04/Q05 验证端口、受控源、功率方向和测试源依据；
- G1-Q06/Q07/Q08/Q09 验证 BJT、三运放、R–2R、555 拓扑和状态转移；
- 关键字段缺失时在 Edge 展示拒答和待补材料，不允许模型补猜唯一数值。

**验收：** 每题保存原图哈希、视觉输出版本、拒答/继续原因、公式/单位检查和最终 Runtime 终态；9 题全部达到 T2，才可标记图片组完成。

### RM-P1-05 组员一教学、批改、学习和治理 G1-Q10～G1-Q14

**任务：**

- G1-Q10：真实备课验证 80 分钟、核心 20 分钟、目标—活动—评价和课程来源；
- G1-Q11：真实批改验证首错、后续有效步骤、评分锚点和人工复核；
- G1-Q12：真实多轮会话验证学生画像、连续路径、并发隔离和恢复；
- G1-Q13：真实科研检索验证时间窗、来源等级和逐条引用；
- G1-Q14：接入独立资产治理 Agent，验证授权、审批、撤回、审计和跨课程可见性。

### RM-P1-06 组员二真实任务 G2-01～G2-17

**科研类 G2-01、G2-06、G2-14、G2-15：**

- 使用真实检索 Provider；保存查询、排除词、候选快照、来源等级和时间窗；
- SiC/GaN、视觉理解、YOLO、RISC-V 侧信道必须逐条核对主题相关性；
- 结论和产业/面积/功耗/精度数字必须能回溯到来源；审核未完成时禁止生成可发布结论。

**教学/学习类 G2-02、G2-03、G2-05、G2-08、G2-12、G2-13：**

- 使用真实备课/学习 Agent，验证时间分配、分层练习、课程资料、个性化触发和导师介入条件；
- G2-03、G2-07 的公式必须同时通过 AST、单位、推理步骤、最终渲染和历史恢复；
- 真实模型截断、审批等待、证据不足和能力缺失必须有不同终态。

**学科诊断/评分类 G2-04、G2-07、G2-09、G2-10、G2-11、G2-16、G2-17：**

- 验证真实 Agent 选择的课程/意图与反馈问题一致；
- G2-04 验证 Verilog 时序报告输入绑定和可恢复失败；
- G2-09 验证四维四等级评分标准，不产生学生分数；
- G2-10/G2-11/G2-16/G2-17 验证首错、CMOS 功耗、BJT 削峰和非理想积分器诊断的确定性校验与真实解释。

## 六、P1/P2：会话、证据、数学和 Runtime 可靠性

### RM-P1-07 会话连续性和并发恢复

- 用双 API Worker、共享 Postgres/Redis/Qdrant 做 Edge 提交、切换课程、断线、恢复和重复提交；
- 验证当前课程摘要、学生身份、资料发布版本和研究证据不会跨会话串线；
- 验证取消、重试和恢复不重复副作用；
- 旧课程摘要、撤回资料和旧研究证据必须在提示词、历史、日志和展示中被过滤。

### RM-P1-08 证据包与最终展示对账

- 每个真实场景生成脱敏语义包和结构包；
- 对账输入/附件哈希、Runtime 请求哈希、终态、Runtime run ID、证据 ID、展示合同和页面截图/状态；
- 任一字段缺失或不一致时阻止“已验收”标记；
- `publishable`、`requires_review`、证据状态、质量缺口在 API、SSE、历史和 Edge 页面保持一致。

### RM-P1-09 数学与科学输出真实质量

- 真实模型结果必须经过受限 AST、单位、符号等价、数值边界和领域规则；
- 公式只存在于 JSON、渲染失败、未知符号、正文/结构化字段不一致时进入待复核；
- 真实 Edge 页面验证行内公式、块公式、复制文本、历史恢复和 SSE 重连后的内容一致。

### RM-P1-10 Runtime/SSE/资源生命周期

- 真实 Provider 运行失败、超时、取消、审批、重试、断线重连和恢复；
- 对账任务、Runtime run、事件、审计和最终展示的终态字段及顺序；
- 清理剩余 SQLite/YAML 资源警告，区分应用、TestClient、Worker 和第三方库责任；
- 真实双 Worker 下验证租约、心跳、幂等键和终态互斥。

## 七、P1/P2：治理和发布门禁

### RM-P1-11 安全与治理真实验收

- 验证学生、教师、管理员、运维角色对调试页、观测接口、原始资料、题库图片、审计和导出的最小权限；
- 验证提示注入、伪造引用、上传恶意文件、撤回资料缓存、CDN/浏览器缓存和错误事件脱敏；
- 验证私有资产、公有课程资料、研究来源和学生作答的授权范围。

### RM-P2-12 发布与环境一致性

- 真实模式启动前执行配置、敏感文件、OpenAPI、Docker Compose、Provider/Flow 和 Agent 发布检查；
- 实际重建镜像并通过健康检查；若 Docker/网络不可用，发布状态必须明确为未验收；
- 生产/准生产环境禁止默认 Mock；Mock 只能通过显式测试配置启用；
- 发布前执行 T0 全量门禁，之后按批次执行 T1/T2/T3，不用 Mock 全量结果替代真实验收。

## 八、执行批次和完成定义

### 批次顺序

1. **B0 环境准入**：RM-P0-01、RM-P0-04；确认真实 Provider、Agent 发布、Flow、RAG、检索和 Edge 文件权限。
2. **B1 真实基础能力**：RM-P0-02、RM-P0-03；先完成六个 Showcase 的真实冒烟。
3. **B2 组员二科研/教学**：G2-01、G2-02、G2-03、G2-05、G2-06、G2-08、G2-12、G2-13、G2-14、G2-15。
4. **B3 组员一图片**：G1-Q01～G1-Q09，逐题保存视觉结构和拒答证据。
5. **B4 组员一业务与治理**：G1-Q10～G1-Q14，接入资产治理真实 Agent。
6. **B5 可靠性发布**：RM-P1-07～RM-P2-12，完成双 Worker、重连、权限和准生产门禁。

### 单场景完成定义

单个场景只有同时满足以下条件才标记 `真实验收通过`：

- Edge 原始输入提交成功，输入/附件哈希可追踪；
- 使用已发布真实 Agent，`provider != mock` 且 `mock_used=false`；
- 路由、能力快照、Runtime run、SSE 事件和终态可关联；
- 结果满足该场景的结构、证据、数学/视觉或诊断门槛；
- `publishable`、`requires_review`、警告和剩余风险在页面与 API 一致；
- 失败、取消、审批等待、证据不足等非成功结果具有正确错误分类；
- 至少一次重试/恢复或对应的明确“不适用”理由被记录；
- 证据包和最终展示版本生成成功，且通过脱敏和审计对账。

### 整体完成定义

- 31 个场景全部达到 T2；涉及 Runtime 可靠性的场景达到 T3；
- 六个 Showcase 不再默认走 Mock，真实模型结果可连续复现并保留差异记录；
- G1-Q01～Q09 完成图片级真实视觉语义验收；
- G2-01/G2-06/G2-14/G2-15 完成真实检索和逐条证据审计；
- G1-Q14 完成独立资产治理 Agent 的权限和发布链；
- Provider、RAG、发布状态、Runtime 和 Edge 的状态源一致；
- Ruff、Mypy、Pytest、配置/敏感文件、OpenAPI、Docker Compose 和准生产检查全部有本轮证据；
- 台账中所有未完成项均按代码缺陷、配置缺陷、证据缺陷、输入缺陷或外部依赖缺陷分类，不得以“Mock 通过”关闭。

## 九、当前明确未完成项

1. RM-P0-01 已从“默认 Mock”推进到“默认 local + 真实 Provider 已配置”，但 Agent 发布状态、Flow ID、能力快照与 Runtime 逐次对账仍未形成完整门禁。
2. RM-P0-02 的同路由结构化截断恢复已完成真实验证，但仍需覆盖不同模型、长输出、重试上限和 Edge 展示一致性。
3. RM-P0-03 的 BGE 文本 embedding、SigLIP 图像模型和 Qdrant 维度兼容性已恢复为 `ready`；RAG 资料质量、撤回/重建索引和科研检索证据仍未全部真实验收。
4. Agent 发布/production-ready、Legacy Runtime 收敛和独立知识治理 Agent 仍需准生产验收。
5. G1-Q01 已在 Edge `/workspace` 完成真实原图上传、真实视觉/求解闭环和 Provider/模型展示复验；但 `visual_acceptance=not_configured`、场景证据审查未执行、数学质量需复核，因此不替代 G1-Q01 T2。G1-Q02～G1-Q09 仍未完成 Edge 图片级语义验收。
6. G1-Q10～G1-Q14、G2-01～G2-17 尚未全部完成真实 Provider + Edge + 证据包验收；G2-05、G2-12、G2-13 已完成真实 Edge/API/Runtime/SSE 对账，但内容证据与人工复核闭环仍未完成，均保持不可发布；科研证据、备课/学习路径和作业诊断仍是主要缺口。
7. 双 Worker、断线恢复、真实 SSE 顺序、并发/幂等、缓存撤回、最小权限和准生产发布仍需 T3 验收。
8. Edge 文件 URL 权限和文件选择链路已恢复；真实 Q01 暴露的剩余问题转为产品/契约缺口：`faculty_course_copilot_v1` 是 text-only 场景，却可被带 `scenario_id` 的工作台 URL 接收图片后提交为 `mixed` 并拒绝；需新增/绑定专用学术视觉场景，不能通过放宽教师场景输入类型掩盖问题。
9. Hugging Face `.no_exist/processor_config.json` 写入警告已通过离线模式消除；当前仅剩第三方 image processor 的 `use_fast` 提示，仍需在准生产门禁中单独分类，不得误记为业务失败。
10. 数据分析真实金丝雀已完成后恢复 `DATA_ANALYSIS_ENABLED=false`；24 行可执行用例真实 DashScope 运行通过，但合成数据、无单位/数据字典和人工复核签字仍保持不可发布。
11. 当前计划文档不改变 `SOLVER_CT` 冻结基线，也不把任何 Mock 结果升级为真实通过。

> 2026-08-22 Edge 真实回归修正：用户确认 Edge 已允许访问文件 URL；在通用 `/workspace` 中成功选择 `Q01_signal_convolution.png`（SHA-256 `a250a31d6150d0438742ed37f889aaedd072ba1389134f292fff92d8052bc8645`），任务 `task_e4cf84d8fa914c5a978e7b5997a70962` 完成，`mock_used=false`、真实模型 `dashscope/qwen3.7-plus`、视觉结构 `complete`。页面初次命中旧静态脚本时把真实 Provider 显示为 `local_graph`；增加 `workspace.js` 版本号并刷新后，页面显示 `实际 Provider=dashscope`、`Runtime 通道=local_graph`、`生成模型=qwen3.7-plus`，与 API 投影一致。该真实任务的 `visual_acceptance=not_configured`、场景证据审查未执行、`quality_gate=partial`、`math_quality=needs_review`（`unsupported_command:Big`），所以仅计真实 Edge/模型/Runtime 回归，不计场景内容通过。

> 2026-08-22 Q01/Q02 专用视觉场景增量：新增 `academic_visual_problem_solver_v1` 与 `academic_visual_spectrum_solver_v1`，把图片输入、视觉验收、结果字段和拒答边界从通用教师场景中分离。Q01 真实 Edge 任务 `task_b404f283dd674a0c9c9bde3a6675b4d1` 使用原图 SHA-256 `a250a31d6150d0438742ed37f889aaedd072ba1389134f292fff92d8052bc8645`，实际模型 `dashscope/qwen3.7-plus`，视觉验收通过、模型完成、数学质量通过；因证据状态为 partial 和人工复核策略，仍为 `completed_with_gaps/publishable=false`。Q02 最新真实 Edge 任务 `task_7ba07093d3e147f7b092b913ebfb7035` 使用原图 SHA-256 `3f53301f52fe1bb3489f4dc6dc14913b4493d135debe4d28cb4ef5904589d4fc`，实际视觉/求解模型均为 `dashscope/qwen3.7-plus`，`visual_acceptance=passed`、`visual_topology_validated=true`、模型完成、`math_quality=passed`、场景字段无缺失；仍因课程确认未完成/人工复核策略保持 `completed_with_gaps/publishable=false`。期间发现并修复视觉门禁把“坐标轴刻度/箭头”等非关键不确定项误判为致命缺失的缺陷，并补充 Lambda/cup 数学符号白名单。两项均为真实 Edge/Provider 证据，不等同于 31 场景整体完成。

> 2026-08-22 Q03 真实模型门控回归：真实图片上传与任务 `task_127a3a3490a543518c7b39f073834641` 完成，`mock_used=false`；视觉阶段实际调用 `dashscope/qwen3.7-plus` 2 次，视觉验收仍为 `blocked`（模型未稳定返回精确频带字段），但用户题干已明确提供频带事实，`prompt_facts_cover=true`。此前下游视觉边界仍只检查 `visual_topology_validated`，导致真实求解被错误跳过；已修复为在“用户文字覆盖验收事实”时允许进入真实求解，同时保留 `visual_acceptance=blocked`、`visual_topology_validated=false` 和 `publishable=false`。修复后同一任务真实求解阶段再次调用 `dashscope/qwen3.7-plus` 1 次并完成，模型输出暴露新的 `math_rendering` 质量缺口，纳入 RM-P1-09，不计 Q03 视觉通过。

> 2026-08-22 G2-16/G2-17 场景契约增量：新增 `academic_text_diagnostic_solver_v1`，绑定组员二 G2-16/G2-17 的纯文本电路诊断案例，避免按课程/意图直接路由时 `scenario_contract=null`。G2-16 真实任务 `task_2c0be8b54551426ea89970a7cee10127` 使用 `dashscope/qwen3.6-flash`，`mock_used=false`、模型完成、答案实际覆盖 6 个结构字段；G2-17 真实任务 `task_55ae950ed6164f978d3c2f92daa2bf5d` 同样使用真实 `dashscope/qwen3.6-flash` 并完成，覆盖非理想诊断、补偿元件和验证步骤字段。两项均保留 `quality_gaps=manual_review`，G2-17 另有 `math_rendering`，均 `publishable=false`。同时新增答案标记驱动的字段可用性映射，缺失字段仍显示缺口，不用固定 Mock 内容补齐。

> 2026-08-22 真实模型优先门禁新增：内部 Agent 结果现在必须同时暴露 `mock_used=false`、真实 `provider/model_route`、请求 ID、usage/latency 和统一 `generation_provenance`；单独的 `mock_used=false` 不再视为真实模型证据。G2-10/G2-11 已用 DashScope `qwen3.5-flash` 完成真实 Provider 回放；G2-10 先暴露 `concept_correction` 缺失，随后修复为仅从模型 `teacher_feedback` 做可追踪字段映射，并以 `task_1f696d5488194a61882acc460dd3dff1` 重测无契约缺失。

> 2026-08-22 G2-09 场景合同与数学质量回归：新增 `rubric_generation_v1/g2-09-fpga-clock-rubric`，真实任务 `task_c63b22090b8841d689825b5a0d7d2ad4` 以 `mock_used=false`、`dashscope/qwen3.5-flash` 完成，四个合同字段齐全且没有学生分数。真实数学复验任务 `task_055bb86b91254358ad543e6ceaffef97` 的 `math_quality=passed`、0 警告；`\sim` 白名单修复已同步 API/Worker。因课程证据不足仍不可发布。

> 2026-08-22 Edge 真实链路增量：Edge 工作台提交 G2-10 产生 `task_5ec21ab6e3584aada03059841c01687b`，任务完成、真实 Provider/模型与场景契约对账一致；26 条事件序号严格递增。浏览器提交后读取结果 DOM 的控制通道再次超时，归类为 Edge 控制/观测缺陷，不把后端真实结果冒充为完整 Edge T2；下一步仍需修复/复验 Edge 结果读取和视觉文件链路。

> 2026-08-22 G2-09 真实模型回归：任务 `task_46a046bc2f024bacac448a3d4f54a43e` 经真实 `GENERAL_QUESTION_V1` 完成，`mock_used=false`、`dashscope/qwen3.5-flash`、1 次模型调用，四个评分维度和四个等级齐全，未生成学生分数。为修复通用 Agent 的适配器/真实 Provider 混淆，`model_execution` 新增 `providers` 列表，展示层支持 Provider/模型列表并投影统一 `generation_provenance`；定向回归 `22 passed, 2 skipped, 2 warnings`。该任务仍需课程边界确认，且暴露 `\\sim` 数学命令未支持，不能标记为可发布通过。

> 2026-08-22 G2-08 真实模型与检索/时长回归：新增 `g2-08-mealy-moore-flipped-classroom` 场景合同；真实任务 `task_54e946f966534eaa8cbdf326612c6f36` 使用 `TEACH_01_LESSON_PREP_V1`、DashScope `qwen3.5-flash`，`mock_used=false`，1 次模型调用，合同字段齐全，`duration_check=pass`（课前20+课内30=50分钟），`math_quality=passed`。本轮修复时间区间误求和、课前/课内时长抽取和 Mealy/Moore 强主题检索锚点，避免 ASM 资料冒充依据；真实结果仍为 `completed_with_gaps/publishable=false`，原因是课程证据和评价标准不足，保留教师审核边界。另发现 Compose 在 `TASK_EXECUTOR_MODE=local` 下 API 内置 Worker 与独立 Worker 争抢 Redis lease，独立 Worker 退出，纳入双 Worker 准生产门禁。

> 2026-08-22 G2-08 最终 Edge 重放：任务 `task_de41531d7f8a4ea2a51888642d8d721d` 经真实 `dashscope/qwen3.5-flash` 完成，`mock=false`、`fallback=false`，30 条事件序号严格递增；真实模型草稿已生成，但证据仍 `insufficient`，并暴露课堂总时长校验警告，保持 `completed_with_gaps`/不可发布。期间修复了展示层只检查旧 `model_execution.status`、漏读 Runtime `generation_provider/generation_model` 的状态判断 bug；新增回归断言，确保真实模型结果不会显示为“未生成模型答案”。

> 2026-08-22 G2-08 时长修复后真实重放：任务 `task_9e627ba9a8f2437893756382aff78f33` 使用真实 `dashscope/qwen3.5-flash`，`mock=false`、`fallback=false`；课前 20 分钟与课内 30 分钟均出现在流程中，`duration_check=pass`、总计 50 分钟，26 条事件序号严格递增并以 `task.completed` 收尾。新增摘要/截止时间去重、课前活动提示词和路由状态展示修复；证据仍 `insufficient`，保持 `completed_with_gaps/publishable=false`。

> 2026-08-22 G2-05 真实模型/RAG/结构化输出复验：新增 `g2-05-bjt-two-week-plan` 场景合同；最终真实任务 `task_299c8879d6aa49e3b33999bfcf7f753b` 使用 `LEARN_01_LOCAL_RETRIEVAL_V1`、DashScope `qwen3.5-flash`，`mock_used=false`，`mode=learning_path_model_generation`。真实 Provider 首次返回对象形状的 `staged_plan`，已增加对象/嵌套周计划到带 `day` 标记数组的结构化恢复；最终输出 14 个计划条目，`plan_horizon_check=passed`（请求14天/计划14天）。同时新增 BJT/三极管命名主题 RAG 覆盖门，拦截 MOSFET/石英晶体等无关片段；最终 `evidence_status=insufficient`、`completed_with_gaps`、`publishable=false`，因此只计真实模型与拒答/降级链路通过，不计内容发布通过。该结果验证“模型真实可用”与“证据充分可发布”必须分开。

> 2026-08-22 G2-12 真实模型/四周周期/人工复核复验：最终真实任务 `task_5bb5130dcb8049dc94d5f7aafaf1b869` 使用 DashScope `qwen3.5-flash`，`mock_used=false`；四个周阶段被规范化为 28 天覆盖，`plan_horizon_check=passed`，课程证据为 `sufficient`。新增场景策略发布门后，因 `manual_review_required=true` 进入 `completed_with_gaps`，`quality_gaps=manual_review_required`、`publishable=false`；未把电源安全和实验条件的教师确认误报为已发布。该场景仍欠 Edge T2 与教师复核证据。

> 2026-08-22 G2-13 真实学习路径复验：初始 API 任务 `task_55f7584f312a483e8a4c86d083424fe2` 使用 `LEARN_01_LOCAL_RETRIEVAL_V1`、DashScope `qwen3.5-flash`，`mock_used=false`。随后补充拉普拉斯/极点/稳定性主题证据门并在 Edge 复跑，最终任务 `task_60dbbc1f5d0a4342923d342badf2d991` 将无关片段正确降为 `evidence_status=insufficient`、`source_refs=[]`，页面显示资料 `0 / 0` 和需要复核；仍保持 `completed_with_gaps`、`quality_gaps=manual_review_required`、`publishable=false`。这验证了结构化模型输出、证据充分性和发布状态必须分开；前后测证据绑定和教师复核仍未完成。

> 2026-08-22 G2-12 Edge 真实链路复验：Edge 任务 `task_90d0b0810bc340529de6822cd77f4ce4` 通过专用场景 URL 提交；页面与 API 均显示 `dashscope/qwen3.5-flash`、`mock_used=false`，四周/28天周期通过，20 条 SSE 序号严格 `1..20`，但 `manual_review_required` 使 `publishable=false`。该场景已完成 Edge/API/Runtime/SSE 对账，教师安全复核仍未完成。

> 2026-08-22 Edge 观测增量：早期 Edge 初始化曾连续超时，随后恢复并完成 G2-05、G2-12、G2-13 专用场景真实提交、结果读取和 API/SSE 对账。G2-13 复跑还确认主题证据不足会在页面保持 `0 / 0` 资料和需复核状态；内容发布门仍未通过，该观测缺口与后端内容结果分开记录。

> 2026-08-22 G2-10 真实 Edge 复跑：任务 `task_c3c47e92b5b34d74a46d45b5f15bfb92` 通过专用场景 URL 完成，页面显示实际 Provider `dashscope`、Runtime 通道 `local_agent`、生成模型 `qwen3.5-flash`，API `mock_used=false`，30 条事件序号严格 `1..30`。真实模型正确指出旁路电容提升交流增益，但同一答案对输入电阻方向同时出现“正确”和“需要改进”，说明字段契约通过并不等于语义一致；新增待办为输出内矛盾检测，发现矛盾必须 `needs_review` 且禁止发布。

> 2026-08-22 G2-10 语义门最终复验：任务 `task_3f3f12c43b4348c08982e40f57214790` 通过真实 Edge 完成，真实 `dashscope/qwen3.5-flash`、`mock_used=false`、26 条事件严格 `1..26`。新增治理门已在 API 记录 `validation_status=warning`、`semantic_consistency=needs_review`，工作台同步展示具体矛盾原因；场景仍保持 `completed_with_gaps/publishable=false`。这证明真实模型输出的字段完整性、语义一致性和发布状态已分层处理。

> 2026-08-22 G2-11 真实 Edge 回放：任务 `task_7d94ed54f7884238b275aefbcdc81656` 使用真实 `dashscope/qwen3.5-flash`，`mock_used=false`，26 条事件严格 `1..26`，页面/API Provider、Runtime、模型和结构化字段一致。模型区分静态与动态功耗并生成频率对比验证题；由于教材证据和参数边界仍需教师确认，保持 `completed_with_gaps/publishable=false`。

> 2026-08-22 G2-16 真实 Edge 回放：任务 `task_9ad6b7419845418a93b614ec3ca2fe30` 使用真实 `ACADEMIC_PROBLEM_SOLVER`、DashScope `qwen3.6-flash`，`mock_used=false`，24 条事件严格 `1..24`。页面/API 输出字段一致并保留安全边界；`quality_gate=partial`、`completed_with_gaps/publishable=false`，确定性工作区和单位规则仍需补齐。

> 2026-08-22 G2-17 真实 Edge 回放：任务 `task_d2978ddb92d7457ab6de4bf96cde892f` 使用真实 `ACADEMIC_PROBLEM_SOLVER`、DashScope `qwen3.6-flash`，`mock_used=false`，24 条事件严格 `1..24`。真实输出保留安全边界，但结构化结果缺少 `compensation_component/diagnostic_steps`，并暴露 `math_quality=needs_review`、`unsupported_command:gg`；页面正确阻止直接发布，后续优先修复字段恢复和数学输出契约。

> 2026-08-22 G2-17 最终复验：任务 `task_73f7739165af4cb083c16c692ce7e42f` 使用真实 `ACADEMIC_PROBLEM_SOLVER`、DashScope `qwen3.6-flash`，`mock_used=false`，24 条事件严格 `1..24`。扩展答案证据标记后 `missing_fields=[]`，`math_quality=passed` 且无 warnings；场景仍因 `manual_review_required` 保持 `completed_with_gaps/publishable=false`，数学质量门与业务发布门保持分离。
