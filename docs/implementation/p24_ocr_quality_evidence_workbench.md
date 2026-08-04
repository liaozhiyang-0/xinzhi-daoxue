# P24：OCR 质量证据工作台

## 目标

把只读 PDF 文本层审计中已经观察到的页数、候选 OCR 页、文本覆盖和复核状态，提供给教师进行证据复核。该阶段不执行 OCR、不写入知识库索引、不批准资料，也不调用真实 Provider。

## 数据边界

- `knowledge_base_manifest.jsonl` 是持久化索引状态，可能落后于最新只读审计。
- `/api/v1/knowledge/ocr-quality-summary` 复用只读 OCR review queue 快照，因此页面级字段来自当前审计快照，而不是把旧 manifest 字段当成最新结果。
- 返回范围是 `read_only_ocr_review_candidates`，不是所有知识库文件的质量结论。
- `ocr_execution_performed=false` 始终保留；候选页只表示文本层审计建议复核或选择，不表示 OCR 已完成。

## 证据字段

每个候选文档展示：页数、候选页号、文本覆盖率（若审计可得）、解析状态、OCR 状态、人工复核标记、优先级和原始 warning。汇总展示候选文档数、候选页数、已知页数、OCR 候选文档数及解析/质量状态分布。

## 当前审计观察

在本阶段审计中，CT 观察到 7 个 OCR 候选文档、169 个候选页；AE 观察到 2 个 OCR 候选文档、41 个候选页。另有超出解析限制的 PDF，需要教师决定拆分、人工检查或后续授权的 OCR 范围。以上是当前只读审计观察，不是 OCR 识别质量或竞赛成果。

## 验证

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe apps/api/app
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q
node --check apps/api/app/static/debug/teacher.js
```

浏览器验收应确认教师工作台显示 OCR Quality Evidence、候选页号和 `OCR executed: no`；切换 CT/AE 时只显示对应课程，DE 仍保持课程边界提示。

## 后续风险

下一阶段需要教师确认哪些资料确实适用 OCR、哪些超限 PDF 需要拆分或人工检查，再设计带证据引用的复核提交流程；在此之前不自动执行 OCR 或把候选页写入运行时索引。
