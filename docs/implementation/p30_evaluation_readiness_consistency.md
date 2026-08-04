# P30：评测报告与 readiness 一致性校验

## 目标

在不把筛选后的评测误判为全量评测的前提下，校验评测报告内部的统计、结果和 provenance 是否一致，并把不一致情况安全地反馈到 CT/AE readiness。

## 校验规则

- `schema_version` 必须是当前支持的 `1.0`。
- `summary.total`、通过/失败/错误/超时/缓存数量必须与 `results` 一致。
- `statistics.by_course` 的课程集合、案例数、通过数和通过率必须与结果中的 expected course 一致。
- 新报告必须校验 `run_metadata.case_count` 和案例 ID SHA-256；旧报告没有 metadata 时标记为 `partial`，不虚构 hash 或运行信息。
- 评测报告只与自身结果集校验，不与完整案例 loader 数量强行比较；`filters` 可以合法地使报告只覆盖部分案例。

## readiness 行为

| 一致性状态 | 处理 |
|---|---|
| `consistent` | 评测 provenance 可作为完整内部一致的离线证据 |
| `partial` | 保留统计，但提示 provenance 元数据不完整 |
| `inconsistent` | 增加高严重度 readiness blocker，不把统计作为可信完成证据 |
| `not_checkable` | 随报告缺失或无效状态处理 |

当前 `latest.json` 的实际结果：CT 13 个案例、AE 1 个案例，报告内部统计一致，但缺少 `run_metadata`，因此两门课程均为 `partial`。完整案例 loader 为 73 个案例；这不构成错误，因为当前报告带有筛选结果，系统不会把它宣称为全量覆盖。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py apps/api/tests/test_evaluation_framework.py -q --no-cov
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe apps/api/app
node --check apps/api/app/static/debug/teacher.js
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\check_sensitive_files.py
```

本阶段只读取现有报告并使用临时测试报告，不重跑或覆盖 `evaluation/reports/latest.json`，不调用真实 Provider。

## 风险与下一步

- 旧报告仍需在授权的离线 mock 评测后刷新，才能从 `partial` 变为 `consistent`。
- 当前一致性校验使用报告结果中的 `expected.course`；后续可以将筛选条件、案例清单版本和 readiness 快照时间纳入更强的跨文件关联。
- 三个演示案例继续保留为用户设计输入，不纳入自动覆盖率或一致性结论。
