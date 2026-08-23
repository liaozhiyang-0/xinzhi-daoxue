# Phase B5：Planner Canary 接管

## 前置条件

只有 B4 明确为 GO 时才允许执行本阶段。若没有 B4 GO 证据，立即停止并报告。

## 目标

让 Planner 在受控 capability / request 范围内成为真实智能决策 Owner，同时保留旧路径回滚。

```text
Request
  ↓
Planner
  ↓
TaskRouter Preflight
  ↓
Canonical Plan
  ↓
Runtime
```

旧路径保留：

```text
Feature Flag OFF
或
Planner Failure / Policy Reject
  ↓
Legacy Route / Overall Router compatibility
```

## Canary 原则

1. 默认 OFF。
2. 按 capability / environment / request metadata 开启。
3. 优先从低风险、已有评测充分的能力开始。
4. Academic high-risk solver 不应作为第一个 canary。
5. Planner failure 必须 fail-safe 到旧路径。
6. planner snapshot、preflight result、canonical plan 必须被持久 trace。
7. resume 使用原 snapshot，不重新规划。
8. 任何 route drift 都必须可审计。

## 必须完成

1. Planner takeover feature flag。
2. capability allowlist。
3. rollback switch。
4. Planner → TaskRouter preflight → CanonicalPlan → Runtime 接通。
5. Planner canary 成功时不再进行第二次智能 route refinement；Planner 未接管时保持旧逻辑。
6. 监控 success rate、route fallback、planner error、plan rejection、latency、cost、terminal failure。
7. contract / SSE / resume / retry / cancel tests。

## 禁止

- 不全量切换；
- 不删除 Overall Router；
- 不删除旧 Router contract；
- 不引入 Skill Framework；
- 不修改 Runtime Kernel；
- 不自动扩大 canary 范围。

## 结束条件

完成一个受控 canary 范围后立即停止，并输出 canary scope、success/failure metrics、fallback metrics、regressions、rollback verification、是否建议继续扩大。

最终回复：

```text
Phase B5 completed.
Planner canary scope: ...
Rollback verified.
No automatic expansion performed.
Stopped before B6.
```
