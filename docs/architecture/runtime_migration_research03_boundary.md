# RESEARCH_03_DATA_ANALYSIS_V1 Runtime 迁移边界契约

本文是 `RESEARCH_03_DATA_ANALYSIS_V1` 的严格评测子任务记录。它只描述迁移候选和结构证据，不启用生产默认迁移，不替代真实 Legacy/Runtime 配对试点，也不修改现有业务实现。

## 1. 当前边界结论

当前系统不是单一路径，而是三层边界叠加：

| 层 | 现有入口 | 当前责任 | 评测结论 |
|---|---|---|---|
| Legacy TaskRunner | `apps/api/app/services/task_runner.py` 的普通 `RESEARCH_03_DATA_ANALYSIS_V1` 分支 | 路由后的检索/上下文、进度事件、Provider 调用、internal-agent 调用、失败降级，以及分析后写作流水线 | 必须保留，直到有授权配对证据证明 Runtime 可以接管对应责任 |
| Runtime 候选 | `RuntimeExecutionBoundary` → `ResearchAnalysisRuntimeService`，仅由 `research_analysis_v2` 选项触发 | 创建/恢复 `AgentRun`，执行 `analysis.execute`，执行 `analysis.verify`，检查结果合同，失败后有限重规划 | 可作为迁移候选，不代表 `V1` 默认已迁移 |
| internal-agent / Provider | `InternalAgentExecutionService` → `DATA_ANALYSIS_LOCAL_V1` 或本地确定性执行器；普通 legacy 路径也可直接 `provider.run` | 实际分析能力、模型解释、表格解析和 V2 分析结果构造 | 仍是 Runtime 执行节点的能力边界；不能把 Runtime 节点误报为独立 Provider-free 科研分析器 |

`apps/api/tests/test_research03_runtime_boundary.py` 用静态结构检查和本地 fake internal-agent 检查以上结论。测试不构造真实 Provider，不读取外部数据，不发起 HTTP/API 调用。

## 2. Legacy 路径中必须保持的行为

在迁移候选未通过授权的 Legacy/Runtime 配对评测前，下列行为是兼容性要求：

1. 普通请求仍以 `RESEARCH_03_DATA_ANALYSIS_V1` 为业务 Agent，不因为 Runtime 服务已注册就自动改变默认执行路径。
2. `TaskRunner` 的任务创建/排队、非阻塞执行、任务状态、进度事件、SSE 顺序和最终结果提交边界保持不变。
3. 已有输入合同、数据质量门禁、授权 manifest/checksum、附件存储和输出 Artifact 约束保持不变；不能通过 Runtime 节点绕过数据授权或质量门禁。
4. Legacy 路径的 Provider/internal-agent 选择、云端授权检查和失败降级语义保持不变。尤其不能把模型生成的统计解释当成确定性重新计算结果。
5. `RESEARCH_03 → RESEARCH_02` 的显式顺序流水线必须继续保留其分析状态边界：只有已验证的分析结果才可作为下一阶段输入；只有计划时必须明确“未实际计算”。
6. 结果中的 `analysis_v2`、`business_data`、provenance、人工复核和限制条件不能因迁移而丢失或改变语义。

这些是“必须保持”的兼容性断言，而不是说 Legacy 结构本身已经适合长期维护。它们应在未来真实配对套件中逐项比较。

## 3. 可以由 Runtime 节点接管的责任

在不改变默认模式的前提下，当前 `ResearchAnalysisRuntimeService` 已提供一个受限候选：

```text
goal
  -> analysis.execute (workflow)
  -> analysis.verify (verification)
  -> finish / bounded replan / fail
```

Runtime 可以接管的责任限定为：

- 将分析目标、成功条件和节点依赖写入可检查的 `AgentRunPlan`；
- 为执行和验证节点提供独立状态、checkpoint、事件和 execution key；
- 从 checkpoint 恢复已保存的 `AgentResult`，避免重启后重复执行已完成节点；
- 在结果失败或验证不通过时依据有限预算重规划，而不是无限重试；
- 在等待用户输入、暂停或等待审批时保持可恢复状态；
- 只在 Runtime 完成且结果状态通过 `RuntimeExecutionBoundary.handoff_result` 时绕过 Legacy 的剩余执行；否则保持 fail-closed，并由发布模式决定是否允许回到 Legacy。

这些责任是编排和生命周期责任。它们不能被扩展解释为 Runtime 已经拥有数据分析方法选择、数据读取授权或模型统计解释能力。

## 4. 仍需 Provider 或 internal-agent 的责任

当前候选中，以下责任仍不能由通用 Runtime 内核自行完成：

- `ResearchAnalysisRuntimeService` 的 `analysis.execute` 节点实际调用 `InternalAgentExecutionService.run`；它不是通用 Runtime tool，也不是独立的纯函数分析节点。
- `InternalAgentExecutionService` 在 `research_analysis_v2` 下可能调用 `DATA_ANALYSIS_LOCAL_V1` 的模型分析路径，或调用本地确定性 `ResearchLocalAnalysisExecutor`。模型路径仍属于 internal-agent/provider 能力，必须保留模型来源、人工复核和独立重算限制。
- 普通 V1 legacy 分支仍可能调用 `self.provider.run`，并在 internal-agent 不可用或失败时按现有策略进入 Provider/降级路径。
- 数据文件读取、授权 manifest/checksum 校验、变量角色解析和 Artifact 生成仍由现有科研分析服务负责；Runtime 只能编排其受控调用，不能自己读取任意路径或接受未登记数据。

因此，迁移候选的正确描述是“Runtime 接管生命周期与验证，internal-agent/Provider 保留能力实现”，而不是“RESEARCH_03 已成为完全 Provider-free Agent”。

## 5. 不改变生产默认的启动契约

本任务定义的候选契约如下：

| 条件 | 预期模式 | 说明 |
|---|---|---|
| 普通 `RESEARCH_03_DATA_ANALYSIS_V1` 请求，没有 `research_analysis_v2` | `legacy` | 生产默认不变，Runtime 服务不应解析该请求 |
| 请求显式带 `research_analysis_v2`，但没有真实发布证据 | `canary` 或被发布门禁压回 `legacy` | 仅用于受控候选/评测，不等于默认迁移 |
| 生产配置将 Agent 设为 `default`，但 Runtime 计划、版本或发布证据不完整 | fail-closed | 不允许静默回退为“看似成功”的 Runtime 结果 |
| Runtime 执行未完成、验证失败或暂停 | 运行记录保持对应非终态 | 不得把非 completed 的结果提交为成功；具体回退由现有 launch policy 决定 |

`research_analysis_v2.execute` 是业务分析合同中的字段，不能单独当作生产发布授权。Runtime 启动意图由现有 `RuntimeLaunchPolicy` 解释；本任务不新增配置、不修改 registry、不修改 roadmap。

## 6. 结构证据与发布证据的区分

本任务测试能够证明的只有结构事实：

- Legacy TaskRunner 中仍能观察到 Provider、internal-agent 和 Runtime boundary 的不同接缝；
- Runtime 候选计划包含执行节点和验证节点，并且 Runtime 服务本身不直接调用 `provider.run`；
- Runtime 可在本地 fake internal-agent 上完成节点状态流转；
- 无 `research_analysis_v2` 的普通请求仍不满足 Runtime 候选的 `supports` 条件；
- synthetic/mock/fixture 的 `RuntimeCanaryEvidence` 不满足 `release_ready`。

这些都不是发布证据。正式迁移至少需要：

1. 经过授权、脱敏、可追溯的 Legacy/Runtime 成对 trace；
2. 同一 Agent 版本和 Runtime plan 版本；
3. 输出合同、状态、Provider/能力来源、checkpoint/recovery 和关键性能门禁均通过；
4. 独立语义评测通过，并与结构报告正确绑定；
5. 发布审批和可回滚策略在真实环境完成。

本文件和新增测试使用的 fake/mock/fixture 只能验证代码边界，不能填充上述任何一项授权发布证据。

## 7. 后续迁移候选的最小切分

后续若要继续推进，应按以下顺序建立新变更，而不是直接重写 TaskRunner：

1. 固定 Legacy V1 输入/输出/事件/Artifact 合同，补齐真实配对 trace 的脱敏与授权流程。
2. 将 `analysis.execute` 的能力实现进一步拆成显式、可审计的本地确定性执行节点和可选模型解释节点；两者分别标记来源，禁止隐式 Provider fallback。
3. 为数据授权、质量门禁和结果验证分别定义节点级输入/输出合同，并验证重试、恢复、幂等和取消语义。
4. 先以 canary 运行并收集真实证据，再考虑 default；没有证据时维持本文第 5 节的 fail-closed 行为。

本评测子任务不执行以上迁移，只记录边界和可验证的下一步。

## 8. Runtime verification checkpoint

The Runtime verification node now parses the typed `ResearchAnalysisResult`
inside the `AgentResult` envelope. The generic `completed` envelope and the
`analysis_v2` marker alone are insufficient. Only `status=executed` can pass
Runtime verification; `planning`, `quality_blocked`, and `insufficient_data`
fail closed, while `needs_review` enters an approval wait. An explicit
`execute=false` request therefore cannot complete a Task or fall through to
Legacy generation. This keeps plan-only output visibly distinct from an
executed analysis result.
