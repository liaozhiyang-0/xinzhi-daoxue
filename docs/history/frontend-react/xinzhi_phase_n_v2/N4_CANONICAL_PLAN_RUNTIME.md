# N4：CanonicalPlan → Runtime 单向执行

## 目标

Runtime 不再重新理解用户目标。

唯一链：

CanonicalPlan → RuntimePlanAdapter → RuntimeTaskEngine → PlanExecutor

## Runtime 禁止

- 再次 course detection
- 再次 intent detection
- 再次 agent selection
- OverallRoutingService
- IntentPlanCompiler recompile
- CanonicalPlan 后 route mutation

## Resume

保持 Phase M 已验证的 durable semantics：

- checkpoint
- Last-Event-ID / SSE
- resume
- retry
- waiting_review
- waiting_user

Resume 不重新 Planner，除非显式 ReplanRequest。

## Replan

允许：

Runtime failure → ReplanRequest → Planner → bounded revised CanonicalPlan → verification → Runtime

必须有限次数、全 trace。

## AC-01 约束

图片事实不足时，Planner/Runtime 都不得为了“完成计划”编造电路事实。

本阶段不 commit。
