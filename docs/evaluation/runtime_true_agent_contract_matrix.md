# Runtime True-Agent Contract Matrix

本文档说明 `test_runtime_true_agent_contract_matrix.py` 对当前 Agent Runtime
所做的 provider-free 合同评测。矩阵验证的是可执行 Runtime 的结构和状态边界，
不是模型答案质量评测，也不是生产发布批准。

对应测试文件：

`apps/api/tests/test_runtime_true_agent_contract_matrix.py`

## 当前状态校准（2026-08-09）

本矩阵覆盖的 Runtime 核心已经实现，而不是待开发设计：

| 能力层 | 当前状态 | 证据边界 |
| --- | --- | --- |
| L1 Runtime Kernel | 已实现 | `AgentRun`/Plan/Node/Observation/Decision/Budget、状态机、DAG 执行与预算/失败传播有 contract tests |
| L2 Durable Run Service | 已实现 | `AgentRunRepository`、durable checkpoint、状态版本、事件关联、恢复、暂停/恢复、审批和 reconcile 有 Runtime/集成测试 |
| L3 Tool/Agent Runtime | 已实现 | `RuntimeHandlerRegistry`、typed tool/Provider/internal-Agent adapter、`RuntimeSubagentRegistry`、handler policy descriptor 和受限 input-schema 校验有 synthetic/provider-free tests |
| L4 Controller Loop | 已实现 | `observe -> decide -> act -> verify -> replan`、fail-closed、预算和控制动作有 synthetic/provider-free tests |
| 生产发布 | 未授权/未完成 | 尚无业务真实 paired trace、semantic sidecar、授权 Canary/default 决策；LangGraph 已确认是冻结 academic solver 的 Legacy/internal 图路径，内部 durable backend 仍未提供 |

这里的“已实现”指代码合同和可重复的 provider-free/synthetic 验证已经存在；它不表示
真实 Provider、Docker、生产 worker 崩溃恢复或生产默认切换已经完成。剩余发布门槛主要
是业务证据、授权决策和路径审计，而不是重新实现上述 Runtime 核心。

## 覆盖矩阵

| 能力域 | 合同证据 | 评测结论 |
| --- | --- | --- |
| General Question observe | `general.observe` 先于后续节点运行，并记录 bounded observation | 覆盖 |
| General Question decide | Runtime controller 产生 `execute`/`replan`，终态由 Run 状态机收敛 | 覆盖 |
| General Question act | `general.tool` 调用注册的 synthetic tool；`general.execute` 通过声明式 typed subagent 调用内部 Agent | 覆盖 |
| General Question verify | `general.verify` 仅在答案存在且结果有效时通过；失败结果不能作为成功答案返回 | 覆盖 |
| General Question dynamic replan | 第一次 subagent 失败后生成带 `.replan.1` 节点的下一版计划，并在预算内再次执行 | 覆盖 |
| Generic Goal observe/decide/act/verify | `RuntimeGoal` 携带 objective、success criteria、capabilities；planner 编译注册能力，Run 仅在声明节点全部成功时完成 | 覆盖 |
| Generic Goal tool/subagent | 能力选择同时包含 read-only tool 与 `RuntimeSubagentDefinition`；subagent target、version 和结果身份进入 observation | 覆盖 |
| Generic Goal dynamic replan | 节点部分失败时依据 `fallback_capabilities` 生成 `goal-runtime-v1.r1` 计划 | 覆盖 |
| Budget | `max_iterations`、tool call 预算和 subagent call 预算在执行前保留；超限时节点失败，不调用 handler | 覆盖 |
| Approval | `requires_approval=true` 的 handler 先让 Run 进入 `waiting_approval`，审批前不执行，审批后恢复同一 Run | 覆盖 |
| Pause/resume | 外部 `PAUSE` 产生 `paused` 状态；再次运行同一 Run 可恢复 pending 节点 | 覆盖 |
| Fail-closed | 失败结果、重规划预算耗尽或预算不足不会被包装成 completed 结果 | 覆盖 |
| Checkpoint identity | checkpoint sequence、state version、run id、launch agent id 和 plan version 可由 `audit_checkpoint_trace` 校验 | 覆盖 |
| Evidence identity | canary payload、checkpoint launch identity 与 evidence identity 不一致时 release gate fail-closed | 覆盖 |

以上“覆盖”均为 synthetic/provider-free contract coverage。尤其是 durable
`AgentRun`/checkpoint/recovery、handler registry、typed subagent 和完整
observe-decide-act-verify-replan 闭环，已经分别在 Runtime contract、recovery、subagent、
observability 和本矩阵测试中落地；“覆盖”不等于真实业务结果已获发布授权。

## RESEARCH_03 迁移证据快照

当前 `RESEARCH_03_DATA_ANALYSIS_V1` 的 `research_analysis_v2` Runtime 候选已经
从两节点扩展为可审计的三节点计划：

```text
analysis.prepare (control)
  -> analysis.execute (workflow)
  -> analysis.verify (verification)
  -> finish / bounded replan / approval / fail
```

已有 `37b3a88 test(runtime): cover research03 prepare checkpoint contract` 覆盖：

- prepare、execute、verify 节点和依赖关系；
- prepare 对请求做 typed validation/normalization，并在 checkpoint control data 中保存
  `research_analysis_prepared` 记录（规范化 payload、execution mode/options 和
  authorization manifest reference）；prepare 完成前不调用 fake internal-agent；
- execute 从 checkpoint payload 恢复，实时修改的请求 payload 不会覆盖已经准备好的输入；
- verify 的失败 bounded replan、`needs_review` 人工审批和旧结果 checkpoint 恢复合同。

对应定向测试在该提交中报告 `23 passed, 2 warnings`，并通过 Ruff、Python 编译检查
和 `git diff --check`。这些是本地 fake/mock/fixture 下的 provider-free 合同证据。
即使 fixture 的 data manifest 含有 `authorized=True`，它也只是被测请求字段，不能
替代真实授权。当前仍缺少：

1. 同一输入、可追溯且经授权脱敏的 Legacy/Runtime paired trace；
2. 绑定相同 Agent version、plan version、suite/case 的独立 semantic judgement
   sidecar/semantic approval；
3. checkpoint/event 审计与真实环境中的发布审批、Canary 决策和回滚记录。

因此 RESEARCH_03 只能标为“implemented + provider-free evaluable”，不能标为
authorized、canary-ready 或 production-default。任何 synthetic、mock、fixture、
readiness 或 provider-free preflight 通过结果，都不得冒充上述真实证据。

## 运行方式

在仓库根目录执行：

```powershell
.venv\Scripts\python.exe -m pytest -q --no-cov apps/api/tests/test_runtime_true_agent_contract_matrix.py
.venv\Scripts\ruff.exe check apps/api/tests/test_runtime_true_agent_contract_matrix.py
```

RESEARCH_03 合同测试（对应 `37b3a88` 的验证范围）为：

```powershell
.venv\Scripts\python.exe -m pytest -q --no-cov `
  apps/api/tests/test_research03_runtime_boundary.py `
  apps/api/tests/test_research_analysis_runtime.py `
  apps/api/tests/test_runtime_agent_contract_matrix.py
```

上面的 `23 passed, 2 warnings` 是 `37b3a88` 提交记录中的既有验证结果；本文件
不将其表述为真实 Provider、真实数据或生产环境验证。

该矩阵只使用内存中的 `AgentRun`、`RuntimeHandlerRegistry`、synthetic tool、
typed subagent double 和序列化 checkpoint record。测试不创建真实 Provider，
不发送 HTTP/API 请求，不读取外部数据，也不需要真实凭据。

## 证据等级与明确限制

本文件和测试生成的是 **synthetic contract evidence**。它们只能证明：

- 当前注册表、计划、预算和状态机在测试输入下遵守声明的 Runtime 合同；
- observe → decide → act → verify 的控制循环能够被结构化 observation、decision、
  node status 和 checkpoint trace 审计；
- 工具、typed subagent、重规划、审批、暂停/恢复和 fail-closed 边界在 synthetic
  handler 下可重复执行；
- checkpoint 与 evidence identity 的错误能够阻断 release gate。

它们不能证明：

- 真实 Provider、模型或检索系统的答案正确性、事实性、语义等价性或安全性；
- 真实网络延迟、成本、吞吐、限流、重试质量或 Provider 可用性；
- 真实学生数据、真实课程数据或生产权限下的工具副作用；
- SSE 顺序/重连、跨进程 durable repository 恢复或生产 worker 崩溃恢复的完整质量；
- 任何 Agent 已经满足 canary 或 production default 发布条件。

LangGraph 当前作为冻结 academic solver 的 Legacy/internal 图路径存在；应用创建时会
为该路径配置进程内 memory saver，但生产配置明确拒绝 memory checkpoint。外层
`AcademicSolverRuntimeService` 可以由 Runtime 控制生命周期和 durable checkpoint，
但这不等于 LangGraph 内部图自身具备跨进程恢复能力。当前决策是保留 Legacy 兼容边界，
不把它宣称为默认 Runtime，也不把内部图的 memory checkpoint 当作生产证据。

尤其是测试中的 `RuntimeCanaryEvidence(kind="synthetic")` 即使结构比较通过，
也必须保持 `release_eligible=False`。它不能替代授权的 Legacy/Runtime 同输入成对
trace、脱敏记录、semantic judgement sidecar、checkpoint 审计和 release preflight。

## 与发布门禁的关系

该矩阵是结构合同层的回归保护，不是发布证据采集器。要进入后续 Canary 判断，仍需
按 `docs/evaluation/runtime_authorized_paired_trace_release_runbook.md` 执行：

1. 获取明确授权，在同一输入下采集 Legacy 与 Runtime 成对结果；
2. 对输入、输出、checkpoint 和事件做脱敏，并绑定 Agent/plan 版本与 run identity；
3. 完成结构 parity、checkpoint audit 和独立 semantic judgement；
4. 运行 collector 与 release preflight，缺失或不一致时保持 fail-closed；
5. 由有权限的发布决策者决定 Canary 或继续保持 Legacy。

测试 fixture 不应被复制到受控 evidence 目录冒充真实 trace，也不能据此修改冻结的
`SOLVER_CT v1.0` 或打开任何生产 default 路径。
