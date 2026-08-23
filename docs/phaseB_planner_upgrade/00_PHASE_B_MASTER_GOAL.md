# 芯智导学 Phase B 总目标：Planner + Canonical Plan 引入

## 1. 阶段定位

Phase A 已完成控制面职责收敛：

- `XZDSupervisor` 保留为 API Adapter / Legacy Compatibility / Trace Compatibility；
- `TaskRouter` 冻结为 Deterministic Preflight Adapter；
- `OverallRoutingService` 冻结并标记为未来 Planner 迁移对象；
- Runtime Kernel、Task/AgentRun、Checkpoint、SSE、Result Pipeline 保持稳定；
- Public Capability / Internal Worker / Skill / Tool 的层级边界已明确；
- Plan 与 State 的未来唯一 Owner 已明确。

Phase B 的目标不是增加新的 public Agent，也不是重写 Runtime，而是建立：

> 一个统一的 Planner 智能决策入口 + 一个 Canonical Plan 边界，并逐步替代当前分散的智能路由和计划解释逻辑。

最终目标架构：

```text
/chat Adapter ─┐
/tasks Adapter ─┼─> PlannerService
Learning Entry ─┘        |
                         v
                 Planner Snapshot
                         |
                         v
                 TaskRouter Preflight
                         |
                         v
                 Canonical Plan
                         |
                         v
                Runtime Plan Adapter
                         |
                         v
                   Runtime Kernel
                         |
                         v
                Business Capability
```

## 2. Phase B 非协商原则

以下大方向不可改变：

1. `PlannerService` 是未来唯一智能目标理解与计划决策 Owner。
2. `TaskRouter` 继续存在，但只作为确定性 preflight / compatibility gate。
3. `Supervisor` 不升级为 Planner，只继续承担 API/legacy/trace 兼容。
4. Runtime Kernel 不重写，不把 Planner 逻辑下沉到 Runtime。
5. 不新增 public Agent ID。
6. 不拆分 `ACADEMIC_PROBLEM_SOLVER` 为课程 Agent。
7. 不改变现有 Task API、Chat API、AgentRequest、AgentResult、Runtime Run/Checkpoint、RAG、Tool、Event 协议。
8. Resume 必须优先恢复 checkpointed planner/plan snapshot，不能重新理解用户目标。
9. Planner 不能绕过 Registry / Preflight / Tool policy / Evidence policy。
10. Planner 初期必须以 shadow mode 进入系统，不能直接替换真实执行路径。
11. 删除 `OverallRoutingService` 只能发生在 Phase B 最后，且必须满足迁移证据与回滚条件。
12. 每一个子阶段完成后立即停止，不自动进入下一个子阶段。

## 3. Codex 可自主调整的范围

Codex 可以根据当前代码事实做以下调整：

- 文件名、类名、内部目录位置；
- Pydantic/dataclass 的具体组织方式；
- additive contract 字段；
- Planner 内部模块拆分方式；
- trace / event 的具体字段命名；
- shadow evaluation 的统计实现；
- 单元测试和 contract test 的组织；
- adapter 的具体落点；
- 为减少重复而做的小范围内部重构。

但必须满足：

- 不改变上述 12 条非协商原则；
- 不破坏旧接口；
- 不跳过 shadow / parity / canary；
- 不为了“简洁”删除 Runtime durability、checkpoint、fallback、SSE 或 evidence gate；
- 不把 Planner 实现成一个新的万能业务 Agent。

## 4. 执行顺序

严格按顺序执行：

1. `B0_contract_and_baseline_freeze.md`
2. `B1_planner_contract_and_owner.md`
3. `B2_canonical_plan_and_adapter.md`
4. `B3_planner_shadow_mode.md`
5. `B4_shadow_evaluation_and_lineage.md`
6. `B5_planner_canary_takeover.md`
7. `B6_overall_router_retirement_and_closeout.md`

不得跳阶段。

## 5. 每个子阶段统一规则

每次只执行当前指定的一个 `.md` 文件。

完成当前阶段后必须：

- 运行该阶段要求的测试；
- 输出变更文件列表；
- 输出新增/修改 contract；
- 输出未完成项；
- 输出风险；
- 明确说明“已停止，没有继续执行下一阶段”。

除非用户显式要求继续，否则不得自动进入下一份计划。

## 6. Phase B 总退出条件

只有同时满足以下条件，Phase B 才算完成：

- `/chat` 与 `/tasks` 可以消费同一种 Planner Snapshot；
- Planner 成为唯一智能目标理解/Agent-Skill-Tool 候选选择 Owner；
- TaskRouter 只承担确定性 preflight；
- Canonical Plan 成为唯一未来计划语义边界；
- Runtime 只消费固定 plan snapshot；
- Planner shadow trace 与旧 route/plan 能够对账；
- 至少完成受控 canary；
- rollback 可用；
- Overall Router 独立控制职责已经退出或只剩明确兼容壳；
- 旧接口 contract tests 通过；
- SSE / retry / resume / cancel / checkpoint 语义没有回归；
- 未新增 public Agent；
- 未进入 Phase C Skill Framework 的正式开发。

Phase B 结束后才进入：

> Phase C：Skill Framework
