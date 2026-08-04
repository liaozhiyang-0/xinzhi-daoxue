# P32：评测案例内容 fingerprint

## 目标

避免只依赖案例 ID 集合判断评测目录是否相同。当案例题干、期望答案、评分规则或其他 `EvaluationCase` 字段变化时，新报告能够留下可追溯的内容 fingerprint。

## 实现

- 对经过 Pydantic 校验的 `EvaluationCase` 做规范化 `model_dump(mode="json")`，按 `case_id` 排序后使用稳定 JSON 编码计算 SHA-256。
- 新增 metadata：
  - `case_catalog_content_sha256`；
  - `case_catalog_content_version=canonical_evaluation_case_payloads.v1`。
- `scripts/run_evaluation.py` 对完整案例目录计算内容 fingerprint，并传入 runner；筛选条件不会改变 catalog content hash。
- readiness 只展示 hash 是否关联，不展示案例原文或 prompt；仍保留原有 ID 集合 hash 和 filters hash。
- 缺少内容 fingerprint 的旧/部分 metadata 报告标记为 `partial`，不会被伪装成完整 provenance。

## 边界

该 fingerprint 表示规范化后的案例模型内容，不是原始 YAML/JSON 字节级 hash；因此格式化、字段顺序变化不会造成无意义漂移，但任何会影响解析后 `EvaluationCase` 的内容变化都会改变 hash。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_evaluation_framework.py apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q --no-cov
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe apps/api/app
node --check apps/api/app/static/debug/teacher.js
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\check_sensitive_files.py
```

P32 不修改现有案例文件、不重跑或覆盖 `evaluation/reports/latest.json`，不调用真实 Provider，也不触碰冻结 Solver 基线。

## 风险与下一步

- 旧报告不会自动获得内容 fingerprint，需要后续明确授权的离线 mock 评测生成新报告。
- fingerprint 目前基于解析后的案例模型，不包含源文件路径和字节级差异；如需审计原始资料变更，可增加独立的 source-file manifest hash。
- 三个演示案例仍由用户设计，不纳入自动优化或覆盖率结论。
