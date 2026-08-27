# 多模态 RAG 集成指南

## 1. 架构与边界

正式调用链为：

```text
POST /api/v1/tasks
  -> TaskRouter
  -> RetrievalPolicy
  -> RAGRetrievalService
  -> BM25 + BGE dense + SigLIP2 visual
  -> Qdrant 强课程过滤
  -> RRF -> BGE reranker -> EvidenceQualityEvaluator
  -> RetrievalContextPacket
  -> 既有 TaskRunner / Local Runtime
  -> CitationValidator
```

生产代码不包含哈希、随机或固定测试向量。测试确定性 Provider 只存在于 `apps/api/tests/rag_fakes.py`。模型或 Qdrant 失败时返回 degraded/failed，并保留 BM25 结果，不会伪装为神经网络检索成功。

`SOLVER_CT_V1` 的原始输入合同属于退役历史资产，不再作为当前业务执行路径。本地仍检索 method/formula/concept/common_error 供日志和界面查看，当前求解统一由 `ACADEMIC_PROBLEM_SOLVER` 的本地 Runtime 处理。

## 2. 安装

CPU（Windows PowerShell）：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "apps/api[dev]"
```

项目依赖包含 `torch`、`transformers`、`sentence-transformers`、`qdrant-client` 和 `Pillow`。CUDA 环境应先按 PyTorch 官方安装方式安装与本机驱动匹配的 CUDA wheel，再安装项目；不要把 CUDA wheel URL 硬编码到仓库。

首次运行会从 Hugging Face 下载模型。默认模型为：

- 文本：`BAAI/bge-m3`
- 图片：`google/siglip2-base-patch16-224`
- 重排：`BAAI/bge-reranker-v2-m3`

模型缓存可通过 `TEXT_EMBEDDING_CACHE_DIR`、`IMAGE_EMBEDDING_CACHE_DIR` 或 `HF_HOME` 放到外部磁盘。Windows 未启用开发者模式时 Hugging Face 不能使用 symlink，缓存会占用更多空间。模型权重、`knowledge_indexes/qdrant/` 和生成缓存均已排除 Git。

## 3. 低资源 CPU 配置

不能稳定运行 BGE-M3 时，必须显式切换，系统不会自动静默回退：

```env
TEXT_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
TEXT_EMBEDDING_DEVICE=cpu
TEXT_EMBEDDING_MAX_LENGTH=512
TEXT_EMBEDDING_QUERY_INSTRUCTION=为这个句子生成表示以用于检索相关文章：
KNOWLEDGE_CHUNK_SIZE_CHARS=300
KNOWLEDGE_CHUNK_OVERLAP_CHARS=50
IMAGE_EMBEDDING_DEVICE=cpu
IMAGE_EMBEDDING_BATCH_SIZE=2
RERANKER_DEVICE=cpu
```

本仓库本次生成的本地 Qdrant 索引使用上述低资源配置。启动前点加载无密钥 profile；它不会修改现有 `.env`：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\scripts\rag_cpu_profile.ps1
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --reload
```

分块器在建库阶段硬切分超长句并控制 overlap；Embedding Provider 会在推理前逐条验证 token 长度，超限即明确报错，不依赖模型截断。

## 4. Qdrant

开发机可使用进程内持久化模式：

```env
QDRANT_MODE=local
QDRANT_LOCAL_PATH=./knowledge_indexes/qdrant
QDRANT_TEXT_COLLECTION=xinzhi_kb_text_v2
QDRANT_IMAGE_COLLECTION=xinzhi_kb_image_v2
```

本地模式采用独占文件锁，不允许多个进程同时打开同一目录。需要并发访问或 payload 索引时使用服务模式：

```powershell
docker compose up -d qdrant
```

```env
QDRANT_MODE=server
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
```

文本 collection 使用命名向量 `text_dense`；图片 collection 使用 `image_visual` 与 `image_caption_dense`。业务层只依赖 `VectorStoreAdapter`。

## 5. 索引 CLI

```powershell
# 审计，不写文件
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py audit

# 基础 Manifest/chunk 与真实文本、图片向量
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py build --full
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py build --rag --text --force-vectors --batch-size 8
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py build --rag --images --course DE --batch-size 2

# 增量、单文件、单图、清理失效 point
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py build --rag --text --images --course CT
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py build --rag --text --course CT --file "relative/path.md"
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py build --rag --images --course CT --image "relative/image.png"
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py build --rag --text --images --delete-stale-points

# 查询与健康
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py query --course CT --text "戴维南定理如何求等效电路" --top-k 3
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py query --course DE --image-query "数电/教材/images/10_0_1.jpg" --top-k 3
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py validate
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py stats
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py health --load-models
```

`rag_index_state.json` 保存 schema/chunker/cleaning/model名称、真实 revision、真实维度、normalize 设置和每个 point 的 checksum。只有版本与 checksum 同时未变化时才复用 point。

## 6. API 与界面

- 正式入口：`POST /api/v1/tasks`
- 管理检索：`POST /api/v1/knowledge/rag-search`
- 健康检查：`GET /api/v1/knowledge/health`
- 安全图片：`GET /api/v1/knowledge/images/{course_id}/{relative_path}`
- 安全文档：`GET /api/v1/knowledge/documents/{course_id}/{relative_path}`

响应可选字段包括 `rag_status`、`evidence_status`、`citations`、`related_images`、`retrieval_trace_id`、`retrieval_latency_ms` 和 `index_version`。调试页显示来源、缩略图、证据不足和降级状态，不显示绝对路径、Qdrant point ID、内部提示词或原始向量。

资源解析只允许 CT/AE/DE 配置根目录内的相对路径，拒绝 `..`、绝对路径和非允许扩展名。

## 7. 验证

```powershell
.\.venv\Scripts\python.exe -m ruff check apps/api/app apps/api/tests scripts/knowledge_base_cli.py
.\.venv\Scripts\python.exe -m mypy apps/api/app
.\.venv\Scripts\python.exe -m pytest -q
$env:RUN_REAL_RAG_TESTS="1"
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_real_rag_models.py -m "integration and slow" -q
```

真实模型测试是可选 slow/integration 测试；普通单元测试只使用 tests 目录内的确定性 fake。测试和生产配置不能指向 fake Provider。
