# P12：OCR 复核决策协议

## 目标

为 P11 生成的 PDF/OCR 候选队列增加可审计的教师决策记录。该协议只描述“教师确认了什么”，不直接执行 OCR、不自动改索引，也不等同于课程材料发布审批。

## 可用决策

- `pending`：尚未处理。
- `request_ocr`：确认需要对候选页执行后续 OCR。
- `split_pdf`：文件超过解析上限，需要拆分或由维护者单独调整配置。
- `approve_existing_text`：教师确认已有文本层可作为后续处理依据；仅允许已成功解析的 PDF。
- `needs_manual_inspection`：需要进一步查看版式、公式或表格。
- `reject_source`：当前来源不纳入课程知识库。

所有非 pending 决策必须填写 `reviewer`、`reviewed_at` 和当前队列中的 `checksum`。文件变化后，旧决策会因 checksum 不一致而失效。

## 可复现命令

先生成队列快照和某门课程的 pending 模板：

```powershell
.\.venv\Scripts\python.exe scripts\generate_ocr_review_queue.py `
  --course CT `
  --decision-template-course CT `
  --output .local_outputs\ct_ocr_decisions.yaml
```

队列 JSON 快照可单独生成：

```powershell
.\.venv\Scripts\python.exe scripts\generate_ocr_review_queue.py `
  --course CT --output .local_outputs\ocr_review_queue.json
```

教师编辑 YAML 后执行校验：

```powershell
.\.venv\Scripts\python.exe scripts\validate_ocr_review_decisions.py `
  --queue .local_outputs\ocr_review_queue.json `
  --decisions .local_outputs\ct_ocr_decisions.yaml
```

校验器返回 `valid=true` 只表示记录结构、文件版本和决策约束正确；即使 `review_complete=true`，也不会自动发布或自动执行 OCR。

## 风险与边界

- 当前队列决策不是数据库审批记录；上传材料仍使用既有材料复核 API。
- 不允许以启发式文本长度伪造 OCR 置信度。
- `approve_existing_text` 不是“内容正确”证明，复杂公式、表格和版式仍需要教师确认。
- 决策文件不应包含学生隐私、真实密钥或未经授权的 OCR 输出。

## 验证入口

```powershell
.venv\Scripts\python.exe -m pytest apps/api/tests/test_knowledge_ocr_review.py apps/api/tests/test_knowledge_api.py -q --no-cov
```

该验证只检查决策 schema、checksum 失效和 API 边界，不执行 OCR、不发布材料、不调用 Provider。
