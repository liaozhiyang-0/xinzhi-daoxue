# 06 效果验证报告（本地工程证据）

本文件只记录本轮实际执行的本地结构、路由和前端冒烟验证，不包含虚构的准确率、收入或用户效果指标。

本轮已执行：

- `scripts/validate_commercial_scenarios.py`：6/6 场景案例、合成标记、人工复核门、商业字段、6步演示和5份案例文档通过。
- `scripts/validate_scenarios.py`：6/6 场景目录与 Agent 能力契约通过。
- `apps/api/tests/test_scenarios_api.py apps/api/tests/test_scenario_catalog.py apps/api/tests/test_scenario_preflight.py`：15 passed，2 warnings。
- `scripts/run_commercial_scenario_preflight.py`：6/6 路由、课程和意图通过；0 provider/network calls；学院治理场景按声明降级到本地 Agent。
- 应用内浏览器：`/demo` 六张场景卡片和每案6个演示步骤可见；备课场景进入 `/workspace` 后任务创建非阻塞，Mock 任务完成并显示“开发演示/本地 Mock Provider”，核心资源与场景 API 均返回200。

未通过/未完成项：

- `scripts/run_web_ui_browser_acceptance.js` 的 Playwright 子步骤因本机缺少 Node `playwright` 包未执行；静态页面/API preflight 19/19 通过。
- Docker 未执行；真实 Provider、教师/研究者试点、市场/价格和官方竞赛规则均未核验。

每次后续填报仍必须同时记录：

- 命令、输入数据集、运行模式和随机种子（如适用）
- 报告路径、运行 ID、案例集合 SHA-256 和实现指纹
- 通过/失败/错误/超时数量及其边界说明
- 是否离线、Mock、本地确定性或真实 Provider
- 人工复核范围、数据授权和未解决风险

建议的本地校验命令：

```powershell
.\.venv\Scripts\python.exe scripts\run_evaluation.py --validate-only
.\.venv\Scripts\python.exe scripts\audit_course_assets.py --course CT --course AE
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\validate_commercial_scenarios.py
.\.venv\Scripts\python.exe scripts\run_commercial_scenario_preflight.py
```

这些命令不等于官方竞赛成绩，也不替代真实用户试用记录。
