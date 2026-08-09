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

## 能力状态投影契约

能力状态投影必须把“能力成熟度”和“发布门禁”分成两个正交维度。当前
`LearningRuntimeCapabilityRead` 已实际投影 `canary_release_eligible`、
`canary_reason` 和 `blockers`；它尚未提供独立的 `status` wire 字段。因此，
本节的 `status` 是评测和 Operator 视图应遵守的规范化语义；在代码增加该字段
之前，不得把它描述成当前 API 已返回的字段。

| 字段 | 规范语义 | 当前 LearningLoop 事实 |
| --- | --- | --- |
| `status` | 能力成熟度标签，只允许按证据阶段解释：`implemented` 表示代码路径、descriptor 和局部合同存在；`evaluable` 表示在此基础上有可重复的 provider-free/结构或离线评测；`authorized` 表示再加上版本绑定的真实 `authorized_paired` trace、独立 semantic sidecar 和发布审批。`blockers` 不是第四种成熟度状态。 | 两个 LearningLoop Runtime 至少为 `evaluable` 的语义状态；它们没有授权证据，不能标为 `authorized`。 |
| `canary_release_eligible` | 只表示共享 `RuntimeCanaryReleaseRegistry` 已按期望的 `agent_version` 与 `runtime_plan_version` 通过结构、语义和版本绑定门禁；查询 provider-free，不执行能力，也不等于 default 授权。 | 当前为 `false`，因为没有授权 evidence。 |
| `canary_reason` | 稳定的门禁原因码，不是质量分数、模型判断或执行结果。当前实现可返回 `canary_release_evidence_missing`、`canary_structural_gate_failed`、`canary_authorized_evidence_missing`、版本不匹配、`semantic_evidence_missing` 或 `canary_release_evidence_approved` 等原因。 | 空 registry 的真实 descriptor 返回 `canary_release_evidence_missing`；缺失版本时 fail-closed 为 `canary_artifact_version_expectation_missing`。 |
| `blockers` | 可行动的独立阻塞码列表，既可描述未实现控制能力，也可描述 disabled、descriptor/evidence 缺失；它不能把已有实现降写成不存在，也不能把 Mock/synthetic 证据升级成授权。 | 至少包含 `learning_runtime_authorized_paired_evidence_missing`；当前还会报告 LearningLoop 尚未实现的 pause/resume/input 控制阻塞。 |

三者不得混同：`implemented` 不代表可重复评测，`evaluable` 不代表获得授权，
`authorized` 也只代表满足 canary 证据门槛，不自动代表 default。当前
LearningLoop 是 provider-free、可评测、无授权证据的能力；因此
`canary_release_eligible=false`，不得进入默认发布。

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
