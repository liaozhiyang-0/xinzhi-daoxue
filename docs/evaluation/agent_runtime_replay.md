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
