# P55：教师复核证据范围与来源说明

## 目标

P54 已把 CT 候选错误签名标记为 `evidence_ready`，但教师工作台和 Promotion 预览还不能直接说明这些证据来自哪个校验器、适用范围是什么。本阶段补齐只读元数据，避免把“校验器证据已存在”误解成“教师已经批准”或“所有自然语言题目都能自动判断”。

## 新增字段

- `deterministic_evidence_scope`：CT 为 `structured_fields_only`，AE 为 `finite_deterministic`。
- `deterministic_validator_id` 与 `deterministic_validator_path`：显示校验器来源。
- `deterministic_evidence_note`：显示有限适用范围说明。

教师队列和 Promotion 摘要复用同一份队列元数据。字段只读，不修改 decision、review evidence、runtime eligibility 或 release 状态。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_error_pool_promotion.py apps/api/tests/test_teacher_web.py -q --no-cov
```
