# Runtime Agent 合同矩阵

本文档记录 `GENERAL_QUESTION_V1` 当前 Runtime seam 的 provider-free 合同测试。
它验证的是 Runtime 的结构、状态机和可控边界，不是模型质量、真实 Provider
等价性或生产发布证据。

对应测试文件：

`apps/api/tests/test_runtime_agent_contract_matrix.py`

## 评测范围

| 合同 | 当前证据 | 结论 |
| --- | --- | --- |
| observe | `general.observe` 节点事实包含 `phase=observe`，并先于后续节点完成 | 已覆盖 |
| decide | Runtime controller 发出结构化 `execute`、`replan` 决策；终态由状态机收敛 | 已覆盖 |
| act | `general.execute` 是显式 typed subagent 节点，执行事实包含 subagent 身份和结果状态 | 已覆盖 |
| verify | `general.verify` 只在结果存在且通过校验时完成 | 已覆盖 |
| retrieve | 通过显式 `retrieve=true` 增加 `general.retrieve` 节点，并保留 retrieval trace | 已覆盖 |
| tool | 通过已注册的本地 fake tool 增加 `general.tool` 节点，工具调用受 Runtime budget 管理 | 已覆盖 |
| subagent | 计划使用 `subagent.GENERAL_QUESTION_V1`，测试只注入 `FakeInternalAgents` | 已覆盖 |
| bounded replan | 失败结果触发版本化 `.replan.1` 计划；`max_iterations=2` 时最多执行两次 | 已覆盖 |
| terminal fail-closed | 默认 Runtime 未以 completed 状态结束时，`handoff_result` 抛出 `NotConfiguredError` | 已覆盖 |

## 运行方式

在仓库根目录执行：

```powershell
.venv\Scripts\pytest.exe -q apps/api/tests/test_runtime_agent_contract_matrix.py --no-cov
.venv\Scripts\ruff.exe check apps/api/tests/test_runtime_agent_contract_matrix.py
```

测试使用 `AgentRun`、`GeneralQuestionRuntimeService`、现有 Runtime
`PlanExecutor`/`RuntimeController`、本地 retrieval fake、注册的工具 fake 和
typed subagent fake。测试不创建 Provider，不发出 HTTP/API 请求，不读取外部数据，
也不需要真实凭据。

## 当前边界记录

### `RESEARCH_03_DATA_ANALYSIS_V1`

当前只把 `RESEARCH_03_DATA_ANALYSIS_V1` 记录为生命周期迁移候选：Runtime
候选计划拥有 `analysis.execute -> analysis.verify`，可以承载 checkpoint、验证和
有界重规划；实际分析能力仍由现有 internal-agent/Provider 边界提供。普通请求仍
保持 Legacy，显式 `research_analysis_v2` 才进入候选路径。该矩阵不把它描述为
已经完成的 provider-free Agent，也不改变默认路由。

### LearningLoop

LearningLoop 当前控制合同是 fail-closed 的 approve-only：只有状态为
`waiting_approval` 时暴露 `approve`；`running`、`paused`、`waiting_input` 以及
所有终态不暴露控制动作。本矩阵不虚构 pause/resume/input 支持。

## 证据限制

本文件和对应测试产生的是 synthetic fixture/结构合同证据。它们只能证明测试中
注入的 Runtime 行为，不构成生产发布证据，不能替代授权的 Legacy/Runtime 成对
trace、真实数据边界检查、语义质量评测或 canary release gate。尤其不能据此提升
任何 Agent 的生产 default，也不触碰冻结的 `SOLVER_CT v1.0`。
