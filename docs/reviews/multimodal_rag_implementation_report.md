# 多模态 RAG 实施报告

报告日期：2026-07-17

## 1. 旧实现清理

- 原哈希伪向量位于已删除的 `apps/api/app/services/knowledge_adapters.py`，旧 chunk 中还存在 `token_hashes` 字段。
- 生产哈希 Provider、`KNOWLEDGE_VECTOR_WEIGHT`、`token_hashes` 生成/读取和旧 `local_lexical_v2_plus_hash_vector` 状态均已删除。
- BM25-like 词项检索保留为独立 `sparse_bm25_v1` 分支，不再被称为 Embedding。
- 确定性假向量仅位于 `apps/api/tests/rag_fakes.py`。

## 2. 文本 Embedding

- 默认配置：`BAAI/bge-m3`，不会自动回退。
- 本机实测显式低资源配置：`BAAI/bge-small-zh-v1.5`。
- runtime revision：`7999e1d3359715c523056ef9478215996d62a620`。
- 维度：512；设备：CPU；L2 normalize：true。
- 文本 point：12,760（CT 5,172、AE 4,409、DE 3,179）。
- 基础分块最大 295 token，超过 512 的 chunk 为 0。
- 核心向量构建耗时：1,059.450 秒；命令总耗时：1,073.768 秒。
- 两次前置失败均被明确记录：第一次旧 chunk 达 977 token；第二次长句/overlap 达 591 token。修正分块器后成功，没有使用截断或伪向量。

## 3. 图片 Embedding

- 模型：`google/siglip2-base-patch16-224`。
- runtime revision：`75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2`。
- 视觉维度：768；caption BGE 维度：512；设备：CPU。
- 图片 point：2,207（CT 1,053、AE 603、DE 551）。
- 失败图片：0。
- 核心构建耗时：CT 349.281 秒、AE 270.888 秒、DE 249.961 秒，合计 870.130 秒。
- 每张图片分别保存真实 `image_visual` 和 `image_caption_dense`；caption 来源优先使用原文上下文，不虚构图片事实。

## 4. 向量存储

- 实测模式：Qdrant local persistent。
- collections：`xinzhi_kb_text_v2`、`xinzhi_kb_image_v2`。
- 最终计数：12,760 text points、2,207 image points。
- 强过滤字段包括 `course_id`，服务模式会创建 payload 索引；本地嵌入模式支持过滤但 Qdrant 提示 payload 索引不生效。
- 索引版本：`RAG_f4e223885aa4c5a003d0`。
- 版本记录包含 schema、chunker、cleaning、模型名、真实 revision、真实维度和 normalize 设置。

## 5. 检索流程

- dense：BGE query -> `text_dense`。
- sparse：现有 BM25-like `sparse_bm25_v1`。
- visual：SigLIP2 text/image -> `image_visual`。
- image caption：相似图片 caption -> BGE 文本检索，并关联 parent chunk。
- fusion：各通道只按名次进入 RRF，不直接相加异构原始分数。
- reranker：真实 `BAAI/bge-reranker-v2-m3`，revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`。本机相关/无关样例得分 0.986873 / 0.000473，排序正确，首次下载加载 270.225 秒。
- evidence：按归一化融合分、来源数和可配置阈值输出 sufficient/partial/insufficient。

## 6. 应用接入

- 正式入口：`apps/api/app/api/v1/tasks.py`。
- 自动 RAG：`apps/api/app/services/task_runner.py` 与 `apps/api/app/services/knowledge_qa_service.py`。
- LEARN 上下文：`RetrievalContextPacket.to_retrieved_context()` 生成 `[S1]` 等证据，`TaskRunner._with_learning_context()` 注入既有文本输入，返回前由 `CitationValidator` 校验。
- SOLVER_CT：冻结云端 Flow 未修改；注册表未提供安全独立 knowledge 字段，因此只检索展示，`solver_rag_generation_injection=false`。
- API：增加 rag-search、health、安全图片/文档资源路由。
- 前端：增加来源、相关图片、证据与降级状态显示。

本地 `.env` 只配置了 SOLVER_CT Flow ID，没有 `XINGCHEN_KNOWLEDGE_QA_FLOW_ID`；同时 LEARN 云端注册项仍是 planned/disabled。因此本轮不能声称真实云端 LEARN 工作流已收到证据。代码注入与引用校验链已完成，正式任务会降级到本地 LEARN RAG。

## 7. 实际测试

- CT 文本：`戴维南定理如何求等效电路`，Top-1 `4.5 戴维南定理与诺顿定理`。
- AE 文本：`负反馈如何稳定放大倍数`，Top-1 `8.6，负反馈放大电路的稳定性`。
- DE 文本：`卡诺图如何化简逻辑函数`，Top-1 `2.4.2 用卡诺图化简逻辑函数`。
- 三个文本查询均为 RAG ready，各返回 3 个文本 hit 和 2 个图片 hit。
- 图片到图片：`kb-image://DE/教材/images/10_0_1.jpg` 的 Top-1 为自身，并回溯到 `数电_第十章.md#chunk-5`，状态 ready、无 warning。
- 正式任务 API：HTTP 202 -> completed；目标 `LEARN_01_LOCAL_RETRIEVAL_V1`；RAG ready；evidence sufficient；5 个 citation；2 张相关图；`retrieved_context` 含 `[S1]`；trace `rag_9863128ad1ce45528df0c6db2d547602`。
- CitationValidator 单测覆盖合法 `[S1]` 与伪造 `[S9]`。
- 降级单测覆盖文本/图片模型失败时 `embedding_status=failed`，且没有哈希回退。

## 8. 修改清单

主要新增：

- `rag_providers.py`、`vector_store.py`、`rag_runtime.py`
- `rag_index.py`、`rag_retrieval.py`
- `citation_validator.py`、`knowledge_resources.py`
- 多模态单元/真实模型测试与本指南、实施报告

主要修改：

- Settings 与 `.env.example`
- knowledge contracts、TaskRunner、KnowledgeQAService、RetrievalContextService
- knowledge API、debug 页面、CLI、Docker Compose、依赖、pytest markers
- 旧基础 indexer：删除哈希字段并强化分块硬上限

依赖新增：`torch`、`transformers`、`sentence-transformers`、`qdrant-client`、`Pillow`。Qdrant Docker 服务固定为 `qdrant/qdrant:v1.18.2`。

## 9. 明确声明

- 已使用真实文本 Embedding：是。
- 已使用真实图片 Embedding：是。
- 已从生产路径移除哈希伪 Embedding：是。
- 已建立真实 Qdrant 向量数据库：是，本地持久化模式。
- 正式任务入口是否自动调用 RAG：是。
- LEARN_01 本地正式降级链是否实际使用证据：是。
- LEARN_01 云端 Flow 是否实际收到证据：否，缺少 Flow ID 且注册项未启用。
- 是否实现文本到图片：是。
- 是否实现图片到图片：是。
- 是否修改原始知识库 Markdown/图片：否。
- 尚未完成：真实云端 LEARN 调用；基于人工标注集校准 evidence 阈值；GPU/CUDA 性能验证。
- 现有 `.env` 未被修改；复用本次 BGE-small 索引时需先点加载 `scripts/rag_cpu_profile.ps1`，否则默认 BGE-M3 配置应重建独立索引。
