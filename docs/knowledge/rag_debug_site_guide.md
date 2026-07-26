# 芯智导学多模态 RAG 调试台使用指南

## 1. 页面与接口

- 页面：`http://127.0.0.1:8000/debug/rag`
- 状态：`GET /api/v1/debug/rag/status`
- 单次链路：`POST /api/v1/debug/rag/run`
- A/B：`POST /api/v1/debug/rag/compare`
- 评测：`POST /api/v1/debug/rag/eval`
- Trace：`GET /api/v1/debug/rag/traces/{trace_id}`

Debug API 复用正式 `TaskRouter`、`RAGRetrievalService`、`RetrievalContextService`、`XingchenCloudProvider` 与 `CitationValidator`，没有第二套星辰客户端或独立聊天入口。真实业务调用仍必须从 `POST /api/v1/tasks` 进入。

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

本机 `.env` 继续保存真实星辰凭据和 Flow；不要把它提交到 Git。生产环境即使误设 `RAG_DEBUG_ENABLED=true`，Debug 写接口仍返回 403。

## 3. 页面功能

### 系统状态

显示 Provider、LEARN configured/published、文本/图片/Reranker loaded 或 lazy、首次加载耗时、Qdrant、point 数、索引版本和 CPU 模式。不显示 Key、Secret、Authorization 或 Flow ID 实值。

### 单条请求

1. 选择 CT、AE 或 DE；
2. 选择意图和回答深度；
3. 默认启用 RAG；
4. 仅需要图证据时勾选“检索图片”；
5. 仅做质量对比时勾选 Reranker；
6. 勾选“允许真实云端调用”才会消费星辰 API；
7. 点击“运行完整链路”。

页面依次展示：路由、查询标准化、BM25、Dense、图片、RRF、Rerank、Evidence、Context、云端、引用校验和最终结果。

### A/B

“A/B 对比”默认运行同题 `RAG vs No RAG`。真正的无 RAG 回答需要允许云端调用；若云端也关闭，B 侧明确返回 `no_rag_no_cloud`，不会偷偷触发本地检索。接口还支持 `cloud_vs_local`。页面只并列回答、引用、耗时与 fallback，不自动断言哪一侧语义更正确。

### 评测集

选择全部、CT、AE、DE、边界或降级，设置 1–60 的 limit。默认不调用云端；如勾选云端，应注意额度与约 20 秒/条的实测延迟。结果提供路由、课程、意图、Top1/Top3 代理、跨课程、citation、fallback、misrouted 已评测数/准确率与 p50/p95 延迟。未开启云端时 misrouted 指标明确返回未评测，不会用本地结果代替。语义正确性仍需人工复核。

## 4. Trace 判读

关键状态：

- `cloud_success`：云端成功并完成本地解析；
- `cloud_partial`：云端完成，但证据为部分支持；
- `cloud_misrouted`：LEARN 拒绝完整求解；
- `cloud_failed`：超时、HTTP、解析或语义 failed；
- `local_fallback`：最终结果来自本地检索整理；
- `rag_degraded`：Dense、图片或 Reranker 的可选通道失败，仍有文本证据；
- `rag_failed`：没有可用证据；
- `citation_validation.failed`：存在 S9 等非法引用或应引用而未引用。

最终结果的 `provider=local` 与免责声明是本地降级的权威标志，不能把它当成云端回答。

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
  allow_cloud = $false
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

# 真实星辰，会消耗额度
$env:RUN_REAL_XINGCHEN_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_real_xingchen_learn.py -q --no-cov
```

## 7. 答辩演示建议

1. 打开状态区，确认 12,760 / 2,207 points 与索引版本；
2. 用 CT 示例先关闭云端，展示 BM25、Dense、RRF、Packet 与本地免责声明；
3. 再开启云端，展示脱敏请求中的 `[S1]`、云端 source references 和 CitationValidator；
4. 用复杂整题展示 `misrouted`；
5. 用无效 Flow 的独立测试实例展示 local fallback；
6. 运行 5 条小评测，再展示 60 条报告结果；
7. 强调页面不显示凭据、绝对路径或向量。
