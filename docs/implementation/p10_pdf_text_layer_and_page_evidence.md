# P10：PDF 文本层与页码证据链

## 目标

在不执行 OCR、不调用外部 Provider 的前提下，让知识库对 PDF 的可检索文本层、页码边界和 OCR 复核候选页形成一致记录。

## 实现边界

- `KnowledgeAuditScanner` 使用 `pypdf` 只读提取 PDF 文本层。
- 每页保留 1-based `page_number`；空页和少于 `PDF_PAGE_TEXT_REVIEW_THRESHOLD` 个字符的页面进入候选页集合。
- 只要存在可提取文本，PDF 可以进入索引，但含候选页时标记 `clean_before_index` 和 `manual_review_required=true`。
- 完全没有文本层、解析失败或超过配置大小限制的 PDF 不进入索引。
- `ocr_confidence` 固定为 `null`，`ocr_confidence_source` 为 `not_available`；当前阶段不把启发式判断当作 OCR 结果。
- PDF chunk 不跨页合并，`ChunkRecord.page_number` 和 chunk metadata 同时保留页码证据；`source_uri` 继续使用兼容现有预览接口的 `#chunk=<n>` 形式。

## 验证命令

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_knowledge_index_pipeline.py apps/api/tests/test_document_ingestion.py -q --no-cov
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy apps/api/app
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py audit
```

最后一条是只读审计；不会写入 `knowledge_indexes/`。如需生成索引，必须由维护者明确执行 build，并复核 OCR 候选页后再纳入教学检索。

## 未完成事项与风险

- 当前没有接入 OCR 引擎，因此扫描型 PDF 仍需人工确认或后续授权的 OCR 工作流。
- 本阶段没有运行 Docker、真实 Provider 或真实用户试用。
- 页面文字提取质量受 PDF 内嵌文本层质量影响；复杂表格、公式和版式仍需教师复核。
