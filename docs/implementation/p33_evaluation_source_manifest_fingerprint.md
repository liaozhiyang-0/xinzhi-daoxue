# P33：评测案例源文件 manifest fingerprint

## 目标

补足 P32 规范化案例内容 fingerprint 的边界：当评测案例目录中的 YAML/JSON 文件发生字节级变化时，报告 provenance 能够关联到源文件 manifest 版本。

## 实现

- 对选定的案例目录递归收集 `.yaml` 和 `.json` 文件。
- 按相对路径排序，将相对路径与文件 bytes 以稳定分隔编码后计算 SHA-256。
- 新增 metadata：
  - `case_source_files_sha256`；
  - `case_source_files_version=evaluation_case_source_files.v1`。
- `scripts/run_evaluation.py` 按 `--suite` 对应的案例根目录计算 manifest hash，并传给 runner。
- readiness 一致性摘要会区分 ID catalog、规范化内容 fingerprint 和源文件 manifest 是否存在。

## 边界与安全

- 只保存 hash，不把 YAML/JSON 原文、prompt、答案或路径列表返回给教师工作台。
- 相对路径会参与 hash，因此文件重命名也会产生变化。
- 这是源文件字节级 fingerprint，不替代 P32 的规范化内容 fingerprint；两者共同帮助区分格式变化与解析后语义变化。
- 现有旧报告保持 `partial`，不会自动重写。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_evaluation_framework.py apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q --no-cov
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe apps/api/app
node --check apps/api/app/static/debug/teacher.js
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\check_sensitive_files.py
```

本阶段不修改案例文件、不重跑或覆盖 `evaluation/reports/latest.json`，不调用真实 Provider，不触碰冻结 Solver 基线。

## 风险与下一步

- manifest hash 目前按案例目录文件计算，不包含外部引用附件的内容；后续若案例附件参与评测，应建立受控附件 manifest。
- 三个演示案例仍由用户设计，不纳入自动评测覆盖结论。
