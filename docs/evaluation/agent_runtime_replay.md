# Agent Runtime 离线回放与评测

Agent Runtime 的 checkpoint trace 可以在不调用 Provider、工具或模型的情况下审计和评测。这样可以把“运行过一次”与“可复现、可验证”分开。

## Trace 格式

```json
{
  "checkpoints": [
    {
      "sequence": 1,
      "state_version": 1,
      "state_data": {"...": "serialized AgentRun"},
      "event_sequence": 0
    }
  ]
}
```

生产 trace 应来自 `agent_checkpoints.state_data`，不要手工修改其中的状态版本。原始 trace 可能包含业务事实，只能放在本地或受控评测存储中。

## 执行评测

```powershell
python scripts/evaluate_runtime_trace.py `
  TRACE.json `
  evaluation/runtime_cases/research_analysis_v1.json
```

退出码为 `0` 表示 trace 审计通过且满足 case；退出码为 `1` 表示 trace 无效或评测失败。输出包含 `audit` 和 `evaluation` 两部分，适合 CI 保存为 artifact。

Case 使用 `case_version` 版本化。新增业务 Agent 时复制一个 case 文件并明确其节点状态、handler、迭代预算和是否强制要求 checkpoint trace；不要把真实凭据或未经脱敏的学生数据提交到仓库。

## Legacy/Runtime Canary

Canary 评测只读取已经捕获的 Legacy/Runtime JSON payload 和 Runtime
checkpoint，不调用 Provider、工具或模型。先用 collector 打包一个已经授权、
脱敏的 paired artifact：

```powershell
python scripts/collect_runtime_canary.py `
  --agent-id GENERAL_QUESTION_V1 `
  --agent-version 1.0 `
  --runtime-plan-version general-qa-v1 `
  --suite-id general-question-canary-20260809 `
  --case-id general-question-001 `
  --authorization-ref change-or-evaluation-record-id `
  --captured-at 2026-08-09T00:00:00+08:00 `
  --legacy LEGACY_RESULT.json `
  --runtime RUNTIME_RESULT.json `
  --checkpoints RUNTIME_CHECKPOINTS.json `
  --output RUNTIME_CANARY_SUITE.json
```

评测报告同时包含 `canary_eligible`（结构与运行指标 gate）和
`release_eligible`（加上授权 paired evidence）。需要阻断 release 时使用明确
的选项：

```powershell
python scripts/evaluate_runtime_canary.py `
  RUNTIME_CANARY_SUITE.json --require-release-eligible
```

旧自动化传入的 `--require-canary-eligible` 仍然可用，但它是
`--require-release-eligible` 的兼容别名，并继续检查 `release_eligible`。不带
任一 gate 选项时，命令仍会输出 JSON 报告，但不会因 gate 失败改变退出码。
collector 在 checkpoint 或结构 gate 失败时不会写入输出 artifact。未评测答案
语义等价性；仍需单独的人评或模型评测。
