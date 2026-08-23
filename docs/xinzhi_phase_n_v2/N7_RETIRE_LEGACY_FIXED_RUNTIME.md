# N7：退休 Legacy Runtime / Fixed Agent Workflow

## 删除前提

必须同时满足：

legacy_runtime_invocation_count = 0
fixed_agent_route_count = 0
targeted regression PASS
six demo PASS

## 如果 invocation > 0

不能直接删。

必须：
缺失 capability binding → 补 handler → replay → 再切。

## Frozen baseline

SOLVER_CT_V1 等历史基线继续只读保存，不参与生产 route。

## scenario_catalog

Phase M 已证明前端六案例依赖 scenario metadata。

因此 scenario_catalog 保留，但职责限定为：
- UI metadata
- goal hints
- default constraints
- presentation profile

不能再硬指定唯一 Agent/workflow。

## Known count tests

删除/修改 legacy scenario 后，必须同步修复 count-based tests，改为语义/能力断言，避免继续依赖脆弱的“场景必须等于 N 条”。

本阶段不 commit。
