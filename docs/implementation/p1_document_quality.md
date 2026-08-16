# P1：课程资料解析质量报告

## 目标

在不改变文件表结构和 Solver 输入协议的前提下，为 TXT/Markdown/DOCX/PDF 的现有解析结果增加统一的 `quality_report`。该报告用于教师复核、发布门槛和后续 OCR/结构化增强，不代表模型准确率。

## 字段语义

| 字段 | 含义 |
|---|---|
| `quality_status` | `ready` 表示已有文本和 chunks；`review` 表示内容为空、结构不足或存在 OCR 页面；`failed` 表示当前无法形成可用文本。 |
| `ocr_required` / `ocr_status` | PDF 存在空白文本层时标记为 `required`；本轮只识别需求，不执行 OCR。 |
| `ocr_confidence` | 未执行 OCR 时固定为 `null`，禁止伪造置信度。 |
| `page_coverage_ratio` | PDF 非空文本页数与总页数之比；非 PDF 为 `null`。 |
| `heading_candidates` | 解析出的 Markdown、章节、例题/习题等标题候选，最多保留 20 条。 |
| `question_count` | 基于题号/例题/习题标记的启发式计数，用于复核提示，不作为题目真值。 |

## 当前边界

- PDF/DOCX 内嵌图片、复杂表格和扫描文字仍需后续 OCR/视觉解析；本轮不声称已完成图文关联。
- `question_count` 和标题识别是规则启发式，不能替代人工审核。
- `ocr_confidence=null` 是诚实状态，不代表 OCR 质量为零。
- 现有 `extraction_metadata` 保持向前兼容，旧字段继续保留。

## 验证

```powershell
$env:APP_ENV = "test"
$env:DEFAULT_AGENT_PROVIDER = "mock"
$env:ALLOW_MOCK_FALLBACK = "true"
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_document_ingestion.py -q
```
