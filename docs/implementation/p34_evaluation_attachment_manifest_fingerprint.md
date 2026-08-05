# P34：评测案例来源与附件边界

## 目标

让离线评测报告能够确认案例源文件集合是否发生变化，同时明确外部图片、PDF 等附件尚未进入当前评测目录，避免把未执行的附件读取或未验证的文件路径描述成真实 provenance。

## 现状审计

- `evaluation/cases/` 当前包含 12 个 YAML 文件、73 个案例。
- 当前 73 个案例均为 `input_type=text`，没有案例使用 `file_refs`。
- 因此本阶段只实现案例源 YAML/JSON 文件的 manifest 指纹，不生成附件指纹，也不为不存在的附件补造路径或内容摘要。
- 三个演示案例仍由用户自行设计，不纳入本阶段自动评测覆盖结论。

## 实现

- 新增 `evaluation_case_source_files_sha256(root)`：递归收集 YAML/JSON，按相对 POSIX 路径排序，将路径和文件字节以稳定分隔编码后计算 SHA-256。
- `scripts/run_evaluation.py` 按 `--suite` 对应的案例根目录计算来源 manifest，并传给评测 runner。
- `EvaluationRunMetadata` 保存：
  - `case_source_files_sha256`
  - `case_source_files_version=evaluation_case_source_files.v1`
- 评测 provenance/readiness 会区分来源 manifest 是否存在；旧报告或缺失 manifest 的报告保持 `partial`，不会被提升为完整一致。
- metadata 仍只保存指纹和版本，不保存案例 prompt、答案、原始 YAML/JSON 或附件路径列表。

## 可复现验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_evaluation_framework.py apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q --no-cov
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe apps/api/app
node --check apps/api/app/static/debug/teacher.js
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\check_sensitive_files.py
```

本阶段不重写 `evaluation/reports/latest.json`，不调用真实 Provider，不修改冻结的 `SOLVER_CT v1.0/SOLVER_CT_V1`。

## 风险与下一步

- 目前没有真实附件案例，因此尚未验证图片/PDF 的路径解析、文件存在性、授权边界和内容指纹。
- 后续若加入附件案例，应先设计受控 attachment manifest：限定根目录、拒绝绝对路径和目录穿越、记录相对路径/大小/字节指纹，并增加重连或报告一致性测试；不能直接把 `file_refs` 原样返回教师端。
