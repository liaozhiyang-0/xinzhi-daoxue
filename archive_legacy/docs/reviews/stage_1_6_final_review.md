# 阶段 1.6 最终审查

审查日期：2026-07-17。分支：`feat/stage-1-6-local-knowledge-qa`。

## 1. 路由表

| course_id | intent | agent_id | route_status | 执行模式 |
|---|---|---|---|---|
| CT | solve_problem | SOLVER_CT_V1 | selected | Mock Provider；星辰未发布 |
| CT/AE/DE | general_qa | LEARN_01_KNOWLEDGE_QA_V1 | selected | retrieval_only |
| CT/AE/DE | explain_concept | LEARN_01_KNOWLEDGE_QA_V1 | selected | retrieval_only |
| AE/DE | solve_problem | UNSUPPORTED | unsupported | 不执行 |
| 其他 | 其他 | UNSUPPORTED | unsupported | 不执行 |

## 2. 修改文件

- `apps/api/app/agents/`：配置驱动的注册表与任务路由。
- `apps/api/app/contracts/`：路由、扩展 KnowledgeHit、RetrievalResult 和 RetrievalContextPacket。
- `apps/api/app/services/`：v1/v2 检索、上下文、证据质量、LEARN_01 与统一 TaskRunner 分支。
- `apps/api/alembic/versions/20260717_0003_task_routing.py`：路由字段增量迁移。
- `knowledge_config/`：三课程元数据、同义词和 OCR 覆盖层。
- `evaluation/knowledge_retrieval/`：15 条草稿、校验、运行、对比与摘要脚本及真实结果。
- `apps/api/app/static/debug/`：课程、intent、路由、事件和 Artifact 调试视图。
- `README.md`、架构、知识库、评测与审查文档：统一当前能力边界。

## 3. 数据库变化

任务表新增：

- `route_status VARCHAR(32) NOT NULL DEFAULT 'selected'`
- `route_reason TEXT NOT NULL DEFAULT ''`

`agent_id` 沿用现有字段，但应用模型不再提供 `SOLVER_CT_V1` 默认值。迁移为增量 `0003`，没有修改旧 migration。

## 4. 检索算法变化

v2 增加 Unicode/大小写归一、课程同义词扩展、精确短语、标题/章节/文件名加权、公式与英文缩写保留、单字与短片段降权、相邻重复去重、单文档上限、来源多样性、最低分阈值和低置信度/无结果警告。

模式名固定为 `local_lexical_v2`；没有加入大型 Embedding 或外部向量数据库，也不声称 semantic/vector。

## 5. 评测集数量

- CT：5 条 draft。
- AE：5 条 draft。
- DE：5 条 draft。
- 合计：15 条，全部来自实际 Markdown 章节，仍需人工审核。

## 6. baseline 指标

`baseline_lexical_v1`：Recall@1 0.800000、Recall@3 0.800000、Recall@5 0.866667、MRR 0.816667、nDCG@5 0.828712、zero_hit_rate 0、wrong_course_rate 0、mean 14.6 ms、p95 24 ms。

## 7. v2 指标

`local_lexical_v2`：Recall@1 0.800000、Recall@3 0.866667、Recall@5 0.866667、MRR 0.822222、nDCG@5 0.833333、zero_hit_rate 0、wrong_course_rate 0、mean 22.266667 ms、p95 35 ms。

## 8. 退化与未召回案例

- 未发现排序指标退化；Recall@1/5 保持不变。
- AE_RET_003 从第 4 位提升到第 3 位。
- AE_RET_001、AE_RET_002 在两个版本中均未进入 top 5，保留为后续人工审核项。
- v2 最终保存运行的平均延迟与 p95 分别增加约 7.67 ms 和 11 ms；15 条草稿下 p95 对单次抖动敏感。

## 9. OCR 清洗草稿

共记录 3 条 draft：AE 1 条、DE 2 条。运行时只应用 `approved`，因此这些草稿没有改变索引，也没有修改原始 Markdown。

## 10. LEARN_01 执行流程

`AgentRequest -> TaskRouter -> LEARN_01 -> KnowledgeBaseService -> RetrievalResult -> RetrievalContextPacket -> EvidenceQuality -> ExplanationArtifact -> AgentResult`。

结果显式显示问题、课程、相关章节、核心检索摘要、建议阅读、`kb://` 来源、证据状态和警告，并声明不是讯飞星辰正式回答。

## 11. 引用完整性

KnowledgeHit 包含确定性 `chunk_id`、相对 `document_path`、SHA-256 `document_checksum` 和 `kb://<course>/<path>#chunk-<n>`。上下文构建拒绝跨课程证据，并保留 Artifact sources。

## 12. 测试结果

最终结果：

- `ruff check .`：通过。
- `mypy apps/api/app`：54 个源文件通过。
- `pytest`：73 项通过，覆盖率 88%；有 1 条 Starlette/httpx 弃用警告。
- `validate_cases.py`：15 条通过，CT/AE/DE 各 5 条。
- `run_retrieval_benchmark.py`：成功生成最后一次 v2 真实结果。
- `export_openapi.py`：成功更新 `docs/api/openapi.json`。
- `check_sensitive_files.py`：通过。
- `docker compose config`：通过。
- `git diff --check`：通过。

## 13. Docker 结果

Docker Engine 29.6.1 下完成：

- 本分支 API 镜像构建成功，并包含 `agent_configs/` 与 `knowledge_config/`。
- 隔离容器使用 SQLite，Alembic 从 0001 升级到 0003 成功。
- CT/AE/DE 三个 general_qa 均完成，路由到 LEARN_01，证据状态 sufficient。
- 每个任务得到 5 个同课程 `kb://` 来源与 12 个有序事件；SSE 终态回放通过。
- 隔离容器未连接 Redis/MinIO，`/health` 为 degraded；这是测试拓扑限制。根 Compose 配置校验通过。
- 用户原有 `xzd-*` 容器未被停止或修改，临时 E2E 容器已删除。
- 全程 `XINGCHEN_ENABLED=false`，没有真实星辰 HTTP 请求。

## 14. 已知限制

- 15 条案例和 3 条 OCR 规则均待人工审核。
- 索引与 TaskRunner 均在 API 进程内，不适合多副本或进程重启恢复。
- 词项检索不能理解图片拓扑、PDF 页码或完整语义。
- 本轮附件未包含最终完整总体架构正文，只能保留既有架构并明确缺口。

## 15. 星辰 API 发布后的接入点

在 `XingchenCloudProvider` 内实现经官方文档确认的鉴权、运行、流式、状态和取消协议；保持 TaskRouter、TaskRunner、AgentRequest/Result、事件与 Artifact 合同不变。发布前继续使用 Mock，禁止猜测 HTTP 字段。
