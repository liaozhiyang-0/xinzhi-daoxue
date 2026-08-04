# P25：OCR 决策证据状态

## 目标

让教师工作台区分 OCR/超限 PDF 决策的“无决策文件、待决、已决但缺证据、checksum 过期或校验失败、已决且有证据”状态。该阶段只读审计，不自动修改 YAML、不执行 OCR、不写入知识库索引。

## 状态语义

- `decision_file_missing`：当前课程没有决策文件。
- `pending`：决策文件存在，但仍有候选项未完成决策。
- `complete_without_evidence`：结构校验完成，但已决行缺少 `evidence_refs`。
- `invalid_or_stale`：校验失败或 checksum 已过期，需要重新生成队列并重新核对。
- `complete_with_evidence`：决策完成、校验通过且已决行都有证据引用。

原有 `validate_ocr_decisions` 协议保持兼容；P25 的缺少证据判断属于 readiness/工作台审计，不会把“缺证据”自动写回决策文件。

## 当前状态

当前 `.local_outputs/ocr_decisions/` 没有 CT/AE 决策文件，因此工作台应显示 `Decision decision_file_missing` 和 `create_pending_ocr_decision_file`。这不代表允许直接执行 OCR，仍需教师提供范围、复核人和证据引用。

## 验证

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe apps/api/app
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py apps/api/tests/test_knowledge_ocr_quality.py -q
node --check apps/api/app/static/debug/teacher.js
```

## 后续风险

决策证据引用仍需要教师或授权维护者提供，系统不会凭页面截图、OCR 置信度或 Mock 输出替代人工证据。三个演示案例仍不纳入自动化决策范围。
