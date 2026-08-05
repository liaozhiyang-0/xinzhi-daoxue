# P31：评测范围与 readiness 时间 provenance

## 目标

增强评测报告与课程 readiness 的关联，使教师能够区分“哪一版案例目录、哪组筛选条件、何时生成的报告”，同时避免把筛选评测误说成全量覆盖或最新结论。

## 实现

- 新生成的 `EvaluationRunMetadata` 增加：
  - `case_catalog_sha256`：完整案例目录 ID 集合 hash；
  - `filters_sha256`：报告筛选条件的稳定 JSON hash。
- `scripts/run_evaluation.py` 在加载完整案例目录后计算 catalog hash，并传给 runner。
- provenance 只读摘要增加报告筛选条件、readiness `snapshot_at`、报告年龄和时间状态。
- 一致性校验增加：
  - metadata filters hash；
  - catalog metadata 是否存在；
  - `completed_at` 是否可解析、是否晚于 readiness snapshot。
- 全默认或旧版 `run_metadata` 不再被误判为有效 provenance；旧报告继续显示 `partial`，而不是错误。

## 当前报告审计

当前 `evaluation/reports/latest.json` 的 CT/AE 统计与结果内部一致，报告完成时间早于 readiness snapshot；但它缺少新版 metadata，因此仍是 `partial`。报告只覆盖筛选后的 CT 13、AE 1 个案例，完整案例目录为 73 个，系统不会将二者混淆。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_evaluation_framework.py apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q --no-cov
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe apps/api/app
node --check apps/api/app/static/debug/teacher.js
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\check_sensitive_files.py
```

本阶段没有重跑或覆盖现有报告，没有调用真实 Provider，也没有修改冻结 Solver 基线。

## 风险与下一步

- 只有后续授权的离线 mock 评测报告才会带上新的 catalog/filter metadata；现有旧报告不会自动升级。
- `case_catalog_sha256` 当前只证明案例 ID 集合关联，不证明案例内容未变；后续可将案例文件内容 fingerprint 纳入独立版本字段。
- 三个演示案例仍由用户设计，不参与自动评测覆盖结论。
