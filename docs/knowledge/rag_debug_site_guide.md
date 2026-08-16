# 芯智导学多模态 RAG 调试台使用指南

## 1. 页面与接口

- 页面：`http://127.0.0.1:8000/debug/rag`
- 状态：`GET /api/v1/debug/rag/status`
- 单次链路：`POST /api/v1/debug/rag/run`
- A/B：`POST /api/v1/debug/rag/compare`（仅本地 RAG 与无 RAG）
- 评测：`POST /api/v1/debug/rag/eval`
- Trace：`GET /api/v1/debug/rag/traces/{trace_id}`

Debug API 复用正式 `TaskRouter`、`RAGRetrievalService`、`RetrievalContextService` 与 `CitationValidator`，没有第二套模型客户端或独立聊天入口。真实业务调用仍必须从 `POST /api/v1/tasks` 进入。

浏览器验收截图：[`../reviews/rag_debug_site_screenshot.png`](../reviews/rag_debug_site_screenshot.png)。

## 2. Windows CPU 启动

PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\scripts\rag_cpu_profile.ps1
$env:RAG_DEBUG_ENABLED = "true"
.\.venv\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir apps/api --host 127.0.0.1 --port 8000
```

Linux：

```bash
export PYTHONPATH=apps/api
export TEXT_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
export TEXT_EMBEDDING_DEVICE=cpu
export IMAGE_EMBEDDING_DEVICE=cpu
export RERANKER_DEVICE=cpu
export RAG_DEFAULT_USE_RERANKER=false
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

本机 `.env` 只保存本地基础设施和可选模型凭据；不要把它提交到 Git。生产环境即使误设 `RAG_DEBUG_ENABLED=true`，Debug 写接口仍返回 403。

## 3. 页面功能

### 系统状态

显示本地 Provider、Runtime 就绪度、文本/图片/Reranker loaded 或 lazy、首次加载耗时、Qdrant、point 数、索引版本和 CPU 模式。不显示 Key、Secret 或 Authorization。

### 单条请求

1. 选择 CT、AE 或 DE；
2. 选择意图和回答深度；
3. 默认启用 RAG；
4. 仅需要图证据时勾选“检索图片”；
5. 仅做质量对比时勾选 Reranker；
6. 点击“运行完整链路”。

页面依次展示：路由、查询标准化、BM25、Dense、图片、RRF、Rerank、Evidence、Context、Local Runtime、引用校验和最终结果。

### A/B

“A/B 对比”默认运行同题 `RAG vs No RAG`。B 侧始终使用本地 Runtime，只关闭检索上下文；页面只并列回答、引用、耗时与 fallback，不自动断言哪一侧语义更正确。

### 评测集

选择全部、CT、AE、DE、边界或降级，设置 1–60 的 limit。评测只走本地 Runtime；结果提供路由、课程、意图、Top1/Top3 代理、跨课程、citation、fallback 与 p50/p95 延迟。语义正确性仍需人工复核。

## 4. Trace 判读

关键状态：

- `local_success`：本地 Runtime 完成并通过结果整理；
- `local_partial`：本地 Runtime 完成，但证据为部分支持；
- `local_failed`：执行、解析或语义校验失败；
- `local_fallback`：最终结果来自本地降级路径；
- `rag_degraded`：Dense、图片或 Reranker 的可选通道失败，仍有文本证据；
- `rag_failed`：没有可用证据；
- `citation_validation.failed`：存在 S9 等非法引用或应引用而未引用。

最终结果的 `provider=local` 与 Runtime 状态是本地执行的权威标志。

## 5. PowerShell 5.1 中文请求注意事项

Windows PowerShell 5.1 的字符串管道可能把中文变成 `?`。调用 API 时显式发送 UTF-8 bytes：

```powershell
$payload = @{
  question = "为什么电容电压不能突变？"
  course_id = "CT"
  intent = "explain_concept"
  use_rag = $true
  include_images = $false
  use_reranker = $false
} | ConvertTo-Json
$body = [Text.Encoding]::UTF8.GetBytes($payload)
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/debug/rag/run" `
  -ContentType "application/json; charset=utf-8" -Body $body
```

浏览器页面与 Python HTTPX 默认使用 UTF-8，不受此问题影响。

## 6. 自动化验证

```powershell
.\.venv\Scripts\python.exe -m ruff check apps/api/app apps/api/tests scripts
.\.venv\Scripts\python.exe -m mypy apps/api/app
.\.venv\Scripts\python.exe -m pytest apps/api/tests -q --no-cov

# 真实模型（CPU）
$env:RUN_REAL_RAG_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_real_rag_models.py -q --no-cov

```

## 7. 答辩演示建议

1. 打开状态区，确认 12,760 / 2,207 points 与索引版本；
2. 用 CT 示例展示 BM25、Dense、RRF、Packet 与本地 Runtime 结果；
3. 用复杂整题展示本地边界与 fallback；
4. 运行 5 条小评测，再展示 60 条报告结果；
5. 强调页面不显示凭据、绝对路径或向量。
