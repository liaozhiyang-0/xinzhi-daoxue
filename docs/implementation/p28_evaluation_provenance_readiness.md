# P28：离线评测 provenance 接入课程 readiness

## 目标

将现有离线评测报告的安全摘要关联到 CT/AE 课程资产 readiness，帮助教师判断课程资产是否有可追溯的评测证据，同时保持评测报告中的答案、提示词、模型轨迹和原始 case 结果不出现在 readiness 接口或教师工作台中。

## 实现范围

- 新增 `course_evaluation_provenance.v1` 只读摘要。
- 通过 `SuiteReport` 校验 `evaluation/reports/latest.json`；解析失败不会被修复或猜测，而是标记为 `report_invalid`。
- 按课程暴露真实的案例数、通过数和报告中已有通过率；没有课程覆盖时标记为 `course_not_covered`。
- 旧报告缺少 `run_metadata` 时保留真实评测统计，但显式标记 `run_metadata_present=false`，并在 readiness 中增加“provenance 不完整”证据缺口。
- readiness 只读取报告，不执行评测、不创建任务、不调用 Provider。
- 教师工作台仅展示报告状态、课程案例数和通过率；`raw_results_included` 固定为 `false`。

## 状态与 readiness 影响

| provenance 状态 | readiness 处理 | 下一步动作 |
|---|---|---|
| `available` | 展示课程统计；若缺少 `run_metadata`，增加中等严重度证据缺口 | `regenerate_evaluation_report_with_run_metadata` |
| `report_missing` | 增加中等严重度证据缺口 | `restore_or_generate_offline_evaluation_report` |
| `report_invalid` | 增加高严重度证据缺口 | `repair_or_replace_offline_evaluation_report` |
| `course_not_covered` | 增加中等严重度证据缺口 | `run_offline_evaluation_for_course` |

该摘要属于离线或本地合成评测证据，不代表真实学习效果、竞赛成绩或正式验收结论。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q --no-cov
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe apps/api/app
node --check apps/api/app/static/debug/teacher.js
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\check_sensitive_files.py
```

P28 不执行离线评测任务，不修改 `evaluation/reports/latest.json`，也不触碰 `SOLVER_CT v1.0` / `SOLVER_CT_V1`。

## 风险与后续

- 当前报告是旧格式，课程统计可用但缺少运行 provenance 元数据；后续评测报告生成流程应补齐 `run_id`、案例集合哈希和实现指纹。
- readiness 仍是证据审计视图，不是运行时课程包发布开关。
- 下一阶段可继续把评测报告生成器的 provenance 写入、报告版本一致性和观测摘要做成独立门禁；三个演示案例仍由用户自行设计。
