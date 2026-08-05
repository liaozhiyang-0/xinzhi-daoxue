# P5 OCR 质量边界

## 现状审计

PDF 文本层解析此前只把完全空页标为 OCR 必需。扫描件中常见的单字符、页眉残片或 OCR 噪声页虽然不是空页，但不足以证明页面正文已经可靠提取。

## 本阶段改动

- 新增共享阈值 `PDF_PAGE_TEXT_REVIEW_THRESHOLD = 20`。
- PDF 页文本长度在 `1..19` 字符时，进入 `ocr_candidate_pages`。
- 空页和低文本页都会触发 `ocr_required`、`manual_review_required` 和 `quality_status=review/failed`。
- 质量报告新增低文本页数量、候选页号和置信度来源字段。
- `ocr_confidence` 仍为 `null`，因为当前没有实际 OCR 引擎或经授权的 OCR 结果；不会把启发式判断伪装成置信度。
- `PDFProcessor` 与上传文档解析复用同一命名阈值，避免两条解析链规则漂移。
- 教师课程材料列表接口 `/api/v1/knowledge/materials` 暴露质量状态、OCR 标记、人工复核标记、候选页号和质量警告，便于发布前复核。
- 教师/管理员可通过 `GET /api/v1/knowledge/materials/{file_id}/chunks` 查看有限的解析片段、页码和来源定位；学生文件所有者权限链不变。

## 风险与边界

短文档页、封面或公式页可能被标为人工复核候选，这是保守策略。它不会自动修改文本、调用 Provider 或把低质量内容阻止为永久失败；教师确认后仍可继续处理。

验证命令：

```powershell
.\.venv\Scripts\pytest.exe apps/api/tests/test_document_ingestion.py apps/api/tests/test_pdf_processor.py -q
.\.venv\Scripts\ruff.exe check apps/api/app/multimodal apps/api/app/services/document_ingestion.py
.\.venv\Scripts\mypy.exe apps/api/app
```
