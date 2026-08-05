# 07 测试脚本与辅助材料

当前可复核入口：

- `scripts/validate_config.py`
- `scripts/audit_course_assets.py`
- `scripts/run_evaluation.py --validate-only`
- `scripts/check_sensitive_files.py`
- `scripts/export_openapi.py`
- `apps/api/tests/`

Current synthetic contest baseline (not official scoring evidence):

- `config/scenarios.yaml` — six commercial scenario contracts.
- `evaluation/cases/contest_scenarios/synthetic_contest.yaml` — three typical cases covering lesson preparation, assignment diagnosis, and research data analysis.
- `scripts/validate_scenarios.py` — scenario catalog and Agent binding check.
- `scripts/validate_contest_cases.py` — evidence fields, synthetic labeling, manual-review gate, and scenario/Agent consistency check.

The baseline is intentionally marked synthetic and requires authorized teacher/researcher review before it can be used as contest evidence. No accuracy, user outcome, or official score is inferred from these files.

提交前应补充与演示案例对应的脱敏输入、预期输出、启动命令、清理命令和浏览器/移动端验证记录。未完成部分保持 `待补充`，不得用 Mock 输出代替。
