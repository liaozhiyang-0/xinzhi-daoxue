# P29：评测报告 provenance 生成链路

## 目标

补齐离线评测报告生成阶段的可复现元数据，避免 readiness 只能读取旧报告的统计而无法确认报告来自哪次运行、哪组案例和哪版实现。

## 实现

- 在 `app.evaluation.reporting` 集中生成 `EvaluationRunMetadata`。
- `EvaluationRunner.run_suite` 为每次运行生成唯一 `run_id`，并写入：
  - 案例数量；
  - 排序后的案例 ID 集合 SHA-256；
  - 评测实现 fingerprint；
  - 固定的进程内 HTTP 执行通道和 bounded metadata-only 轨迹保留策略。
- 元数据构造函数不接收、不保存 prompt、answer 或原始 case 结果。
- 旧的 `evaluation/reports/latest.json` 不被自动重写；其缺少 `run_metadata` 的状态继续由 P28 readiness 逻辑标记为 provenance 不完整。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_evaluation_framework.py -q --no-cov
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe apps/api/app
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\check_sensitive_files.py
```

本阶段使用临时报告目录进行 runner 测试，不执行真实 Provider，不覆盖项目现有评测报告。

## 风险与下一步

- 已存在的旧报告仍需在明确授权的离线 mock 评测运行后才会获得新 metadata；本阶段不擅自重跑并覆盖报告。
- 目前 fingerprint 复用评测缓存 fingerprint；若后续增加新的影响评测结果的配置，应同步纳入 `evaluation_fingerprint`。
- 下一阶段可增加报告版本一致性检查和“报告 metadata 与 readiness 快照”的时间/案例集合校验。
