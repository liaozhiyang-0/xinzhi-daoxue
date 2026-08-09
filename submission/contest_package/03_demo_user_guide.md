# 03 Demo 使用说明

五个待打磨商业案例的逐案演示脚本位于 `docs/commercial_cases/`：

- `faculty_course_copilot_v1.md`
- `assessment_diagnosis_v1.md`
- `student_learning_path_v1.md`
- `research_data_workbench_v1.md`
- `department_knowledge_governance_v1.md`

科研前沿案例为已完成基线，运行时与证据边界见 `apps/api/app/services/research_frontier_service.py` 和 `docs/implementation/p61_contest_scenario_catalog.md`。

每个场景在 `config/scenarios.yaml` 中有6个独立演示步骤，前端 `/demo` 从场景目录读取步骤、买方、交付价值和运行预检；点击后进入 `/workspace?scenario_id=...`，任务创建保持 `202` 非阻塞。演示输入只使用脱敏或合成内容，Mock/本地 fallback 必须在页面状态中显式标注。

## 可复现检查

```powershell
$env:PYTHONPATH = "apps/api"
.venv\Scripts\python.exe scripts\validate_scenarios.py
.venv\Scripts\python.exe scripts\validate_commercial_scenarios.py
.venv\Scripts\python.exe scripts\run_commercial_scenario_preflight.py
.venv\Scripts\python.exe -m pytest apps\api\tests\test_scenarios_api.py apps\api\tests\test_scenario_preflight.py -q --no-cov
```

## 演示边界

- `production_ready=false` 只能演示本地 Agent、Mock 或声明的 fallback，不得描述为真实 Provider 结果。
- 证据策略要求人工复核时，必须展示 `pending_manual_review`/`needs_manual_review`，不得自动发布。
- 未提供真实数据时，数据分析案例只能展示计划或 `insufficient_data`。
- 没有授权的学生资料、课程原始 YAML、密钥和 Flow ID 不进入提交包。
