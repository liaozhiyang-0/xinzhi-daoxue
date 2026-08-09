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

LearningLoop readiness 的版本与发布投影合同如下：

| 字段/能力 | 代码与测试证据 | 当前结论 |
| --- | --- | --- |
| `agent_version` | 两个 Runtime service 显式声明 `learning-agent-v1`；`RuntimeCapabilityDescriptor` 保留并序列化该字段；`test_runtime_capability_descriptor.py` 与 `test_learning_runtime_release_readiness.py` 验证真实 descriptor 投影 | 已实现、可核验；不是授权证据 |
| `runtime_plan_version` | `plan_version` 分别为 `teaching-interaction-v1` / `learning-progress-v1`；readiness 投影优先读取 descriptor 字段，否则回退到 descriptor `version` | 已实现、可核验；必须和 evidence identity 绑定 |
| `canary_release_eligible` / `canary_reason` | `/api/v1/learning/runtime-readiness` provider-free 查询共享 `RuntimeCanaryReleaseRegistry`；空 registry 的真实 descriptor 返回 `canary_release_evidence_missing` 并保持 false | 可评测但未授权 |
| 缺少版本的 fail-closed | readiness release 测试确认不会从 artifact 或 plan version 反推缺失 `agent_version` | 已覆盖负向合同 |
| authorized evidence | 需要真实同输入 Legacy/Runtime trace、`authorized_paired` structural suite、semantic sidecar、显式 expected versions 和独立审批 | 当前缺失；不得 canary/default |

这里的“已实现/可核验”只表示代码和 provider-free 合同存在。测试中构造的
registry、Mock/local 执行器、synthetic payload 和 readiness 字段不能填充
authorized evidence，也不能把 LearningLoop 标记为已完成生产迁移。

## LearningLoop 后续迁移证据矩阵

| 能力 | Runtime 实现 | 结构/离线评测 | 真实授权门槛 | 当前状态 |
| --- | --- | --- | --- | --- |
| Teaching 三动作 | `TeachingInteractionRuntimeService` 的 observe/apply/verify/approval DAG 与领域结果交接 | descriptor/readiness/approval contract tests | 同输入 Legacy/Runtime paired trace + 领域 semantic sidecar + 发布审批 | 实现、可局部评测、未授权 |
| LearningProgress 四动作 | `LearningProgressRuntimeService` 的 observe/apply/verify/approval DAG 与领域结果交接 | descriptor/readiness/runtime contract tests | 幂等、掌握度/重测结果 paired trace + semantic sidecar + 发布审批 | 实现、可局部评测、未授权 |
| capability identity | `agent_version=learning-agent-v1` 与各自 `runtime_plan_version` 已显式声明 | descriptor/readiness tests 与 evidence intake contract | suite、checkpoint、sidecar、preflight 的版本完全一致 | 实现、可核验、未授权 |
| Legacy → Runtime 默认切换 | `LearningLoopService` 保留 Legacy/Runtime 分流 | offline collector、replay audit、release preflight schema | authorized release record、canary 观察、回滚配置和独立 default 审批 | 未完成 |

## 证据限制

本文件和对应测试产生的是 synthetic fixture/结构合同证据。它们只能证明测试中
注入的 Runtime 行为，不构成生产发布证据，不能替代授权的 Legacy/Runtime 成对
trace、真实数据边界检查、语义质量评测或 canary release gate。尤其不能据此提升
任何 Agent 的生产 default，也不触碰冻结的 `SOLVER_CT v1.0`。
