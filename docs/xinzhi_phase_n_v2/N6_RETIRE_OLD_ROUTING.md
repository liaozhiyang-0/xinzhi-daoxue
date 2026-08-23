# N6：退休 Overall Router 与 IntentPlanCompiler 默认权力

## OverallRoutingService

只有在：
- controlled takeover 稳定；
- rewrite telemetry 已明确；
- Planner 覆盖对应任务；

后才执行：

1. 从 RuntimeRequestPreparation 移除；
2. 禁止 CanonicalPlan 后 route rewrite；
3. 保留短期 audit stub；
4. zero importer 后删除。

## IntentPlanCompiler

降级为：
- old checkpoint reader
- legacy adapter

正常新任务不得再由它生成默认生产 plan。

## TaskRouter

降级为 deterministic preflight / compatibility mapper。

只允许：
- unsupported input
- capability availability
- coarse hint
- legacy alias

不得决定最终业务执行目标。

## FallbackRoutingService

收敛到：
Planner fallback policy + Runtime execution fallback policy

避免第三 route owner。

本阶段不 commit。
