# Phase B4：Shadow Evaluation、Parity 与 Lineage 对账

## 目标

用真实/离线任务 trace 判断 Planner 是否具备接管资格。本阶段重点是评估，不扩大控制权。

## 必须完成

1. 建立 Planner Shadow evaluation suite。
2. 至少覆盖 Academic Solver、Knowledge QA、Teaching、Research、General Question / fallback。
3. 评估 route parity、intent/course parity、capability selection、plan validity、invalid target rate、unsupported skill/tool selection、latency、model cost、planner failure rate、route drift。
4. 对 disagreement 分类：
   - old route wrong / planner better
   - planner wrong / old route better
   - both valid
   - insufficient evidence
   - availability/fallback difference
5. 建立 route/plan/context lineage 对账报告。
6. Planner 提议的候选必须经 TaskRouter/Registry deterministic preflight 校验。
7. Planner 不得因一次样例胜出就获得接管资格。

## 接管门槛

Codex 必须根据现有评测规模和系统风险提出量化阈值。阈值可以调整，但至少包含：

- invalid target rate
- unsupported capability rate
- critical routing regression
- planner error rate
- latency/cost overhead
- resume/rollback integrity

并形成明确 `GO / NO-GO` 判断。

## 禁止

- 不删除 Overall Router；
- 不默认启用 Planner takeover；
- 不修改 public Agent 数量；
- 不进入 Experience Memory；
- 不自动根据评测修改 prompt/策略并直接上线。

## 交付物

- evaluation cases
- parity report
- disagreement taxonomy
- Planner takeover readiness report
- GO/NO-GO conclusion

## 结束条件

若 NO-GO：给出修复项，不进入 B5。
若 GO：仍然停止，等待用户显式指令执行 B5。

最终回复：

```text
Phase B4 completed.
Planner takeover readiness: GO / NO-GO.
No takeover performed.
Stopped before B5.
```
