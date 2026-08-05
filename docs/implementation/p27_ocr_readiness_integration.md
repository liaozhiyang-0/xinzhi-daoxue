# P27：OCR 决策证据纳入课程资产 readiness

## 目标与现状

P25/P26 已提供 OCR 质量审计、教师决策证据状态和受控 YAML 写回。P27 将同一只读 OCR 快照接入 `GET /api/v1/knowledge/course-asset-readiness?course_id=CT|AE`，避免 readiness 只显示课程资产和错误模板状态，却遗漏 PDF/OCR 决策边界。

## 状态映射

当课程存在 OCR 候选文档时，以下状态会成为高优先级 readiness blocker：

- `decision_file_missing` → `knowledge_ocr_decision_file_missing`；
- `pending` → `knowledge_ocr_decisions_pending`；
- `complete_without_evidence` → `knowledge_ocr_decisions_missing_evidence`；
- `invalid_or_stale` → `knowledge_ocr_decisions_invalid_or_stale`。

`complete_with_evidence` 不新增阻塞项，但也不代表 OCR 已执行、索引已发布或课程效果已验证。若没有 OCR 候选行，缺少决策文件不会制造无意义的阻塞。

教师工作台的 Course Asset Readiness 卡片现在展示 OCR 决策状态、候选数量和缺少证据引用的行数；OCR 质量面板仍保留页面级详情。

## 安全与边界

- readiness 复用 OCR review cache，不执行 OCR、不调用 Provider、不改写决策文件；
- 不修改 `SOLVER_CT v1.0/SOLVER_CT_V1`；
- readiness blocker 只阻止“证据就绪”声明，不自动批准 OCR、索引或发布；
- 三个演示案例仍由用户设计，不在本阶段自动生成或评估。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py apps/api/tests/test_knowledge_ocr_quality.py -q --no-cov
.\.venv\Scripts\ruff.exe check .
node --check apps/api/app/static/debug/teacher.js
.\.venv\Scripts\python.exe -m mypy apps/api/app
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\check_sensitive_files.py
```

## 风险与后续

真实 CT/AE 决策文件尚未由教师提交时，readiness 会持续显示对应 blocker；这是当前事实，不是失败指标。下一阶段可将 readiness 快照与离线评测报告的 provenance 关联，但仍需保持“本地/Mock 结果显式标记”和真实 Provider 授权边界。
