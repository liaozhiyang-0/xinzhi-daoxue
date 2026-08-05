# 场景运行时可观测性与性能基准

## 运行时摘要

通过场景目录绑定的请求会在任务选项中保留：

- `scenario_id`、版本和目标 Agent；
- 场景检索画像与证据策略；
- 外部检索后的 `scenario_evidence_review`；
- 本地任务结果中的 `structured_result.scenario_id`。

无场景请求不会继承用户伪造的场景保留字段。带有图片、PDF 或混合附件的旧任务入口会先推断真实输入类型，再与场景声明的 `input_modes` 比较。

## 本地微基准

```powershell
.venv\Scripts\python.exe scripts\benchmark_scenario_catalog.py --iterations 1000
```

该基准分别测量 `AgentRequestV2` 与旧 `/tasks` 入口的本地场景绑定，不访问网络、不调用 Provider。一次观测示例：

```text
V2 p50 5.2 us / p95 8.7 us
legacy p50 7.3 us / p95 13.1 us
catalog 6
network_calls 0
provider_calls 0
```

这些数字只用于发现本地绑定回归，不代表端到端任务延迟、模型质量或竞赛准确率；运行环境变化后应重新执行。

演示前可调用 `GET /api/v1/scenarios/{scenario_id}/preflight`。返回值区分主 Agent 生产可用、声明的 fallback 可演示、Mock 可演示和完全不可用；`production_ready` 只在主 Agent 真实运行可用时为真。

## 验证入口

```powershell
.venv\Scripts\python.exe scripts\validate_scenarios.py
.venv\Scripts\python.exe scripts\validate_commercial_scenarios.py
.venv\Scripts\python.exe -m pytest apps\api\tests\test_scenario_catalog.py apps\api\tests\test_task_router.py apps\api\tests\test_task_api.py -q --no-cov
.venv\Scripts\python.exe scripts\run_commercial_scenario_preflight.py
# 该预检同时核验 Agent 路由、课程绑定、默认意图，并保证不调用网络或 Provider
```
