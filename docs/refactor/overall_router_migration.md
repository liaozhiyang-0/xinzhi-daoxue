# OverallRoutingService 迁移边界

## 1. 结论

`OverallRoutingService` 本阶段不删除，但标记为 `Deprecated Future Planner Candidate`。它是过渡期的二次路由实现，不是长期控制面。

处理分类：

| 对象 | 处理 | 说明 |
| --- | --- | --- |
| `OverallRoutingService` | FREEZE / DEPRECATE | 保留兼容和回滚，不继续增加 routing 逻辑 |
| `OVERALL_ROUTER_LOCAL_V1` | FREEZE | 保留内部模型角色，不提升为 public Agent |
| `overall_route_candidates()` | KEEP（过渡） | 为模型路由限定候选边界 |
| `apply_overall_route()` | KEEP（过渡） | 统一把结果重新校验为 `RouteDecision` |
| 独立模型路由 owner | MERGE（未来） | 迁移到 Planner 的候选选择阶段 |

## 2. 当前执行路径

`RuntimeRequestPreparationService.prepare()` 在非 resume 场景中可能执行：

```text
已选 RouteDecision
  -> OverallRoutingService.route()
  -> TaskRouter.overall_route_candidates()
  -> InternalAgentHub.run_text(OVERALL_ROUTER_LOCAL_V1)
  -> OverallRouteDecision 校验
  -> TaskRouter.apply_overall_route()
  -> 重新组装 Context
  -> 重新编译 IntentExecutionPlan
  -> AgentExecutionPlanner.build()
```

它会带来三个控制面问题：

1. 任务创建阶段已经有一次 deterministic route，Runtime 准备阶段又可能改 Agent、课程和意图；
2. route 改变后 Context 和 IntentExecutionPlan 需要重新构造，存在重复解释；
3. 内部 Router 模型参与业务控制，但其结果还必须依赖 TaskRouter 二次校验。

## 3. Phase A 处理

只做边界标记，不改变调用结果：

- 在 `OverallRoutingService` 类定义附近增加 TODO，明确未来由 Planner 替代其“总体路由”职责；
- 不增加新的 prompt、candidate、fallback 或 route mutation 规则；
- 继续保留 timeout、schema validation、invalid target、provider error 的 fail-safe fallback；
- 不删除内部 Agent ID，不修改 `InternalAgentHub` 的公共调用契约；
- 不在 resume 场景重新调用它，继续遵守 checkpointed request/plan 优先原则。

TODO 的语义是 owner 迁移提示，不是本阶段实现 Planner 的许可。

## 4. 未来 Planner 替代条件

删除或关闭独立 Overall Router 前必须完成：

1. Planner 的目标/候选/计划契约已定义并通过离线 route parity；
2. deterministic route、Overall route、Planner route 的 lineage 可对账；
3. 至少一个版本周期内，失败率、route drift、延迟和成本有可比较 trace；
4. fallback 和 rollback 已验证；
5. API、Event、Runtime Plan/Run、RAG/Tool contract 不需要破坏性迁移。

## 5. 兼容性

- `OverallRoutingOutcome`、`RouteDecision` 和 route trace 字段保持兼容。
- Overall Router 未使用、超时或返回非法目标时继续返回当前 route。
- 任何配置关闭 Overall Router 时，任务仍可经本地 deterministic route 完成 preflight。
