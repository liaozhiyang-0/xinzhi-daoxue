# Runtime True-Agent Contract Matrix

本文档说明 `test_runtime_true_agent_contract_matrix.py` 对当前 Agent Runtime
所做的 provider-free 合同评测。矩阵验证的是可执行 Runtime 的结构和状态边界，
不是模型答案质量评测，也不是生产发布批准。

对应测试文件：

`apps/api/tests/test_runtime_true_agent_contract_matrix.py`

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

## 运行方式

在仓库根目录执行：

```powershell
.venv\Scripts\python.exe -m pytest -q --no-cov apps/api/tests/test_runtime_true_agent_contract_matrix.py
.venv\Scripts\ruff.exe check apps/api/tests/test_runtime_true_agent_contract_matrix.py
```

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
