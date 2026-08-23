# Phase B6：Overall Router 退出与 Phase B 收尾

## 前置条件

必须同时满足：

- B4 = GO；
- B5 canary 稳定；
- rollback 已验证；
- `/chat` 与 `/tasks` 均能消费 Planner Snapshot；
- Planner → Preflight → Canonical Plan → Runtime 已稳定；
- 无严重 route regression。

否则不得执行删除或关闭。

## 目标

完成控制面的最终收敛：

```text
Supervisor = API/Legacy/Trace Adapter
Planner = 唯一智能决策 Owner
TaskRouter = Deterministic Preflight
Canonical Plan = 唯一计划语义边界
Runtime = 执行与恢复 Owner
```

## 必须完成

1. 将 `OverallRoutingService` 从默认智能控制路径退出。
2. 视调用证据选择保留 compatibility wrapper、标记 deprecated，或删除无调用实现。
3. `OVERALL_ROUTER_LOCAL_V1` 不再作为独立控制 owner；如需回滚可暂时保留内部 ID。
4. 清理 Planner 已取代的重复 route/context/plan mutation。
5. 保持 TaskRouter 的 deterministic preflight。
6. 更新架构文档。
7. 完成 Phase B regression。
8. 输出 Phase C Skill Framework 的接入点，但禁止开始实现。

## 重点清理对象

仅在有测试证据时处理：

- independent Overall Router control path
- duplicated route refinement
- duplicated plan interpretation
- Supervisor 中已无必要的智能判断分支
- 重复 context rebuild

不得为了减少文件数而删除兼容 adapter。

## Phase B 最终验收

必须通过：

- contract tests
- unit/integration tests
- SSE sequence/reconnect
- retry/resume/cancel
- checkpoint compatibility
- planner shadow/canary tests
- route lineage tests
- rollback tests
- representative evaluation suite

并确认：

- 未新增 public Agent；
- Runtime Kernel 未被重写；
- Planner 已成为唯一智能决策 Owner；
- Overall Router 不再是平行控制面；
- Canonical Plan 成为未来唯一 plan boundary；
- Phase C 尚未启动。

## 最终交付物

- `docs/architecture/planner_phase_b_final.md`
- `docs/audits/planner_phase_b_closeout.md`
- 最终控制流图
- KEEP / MERGE / FREEZE / REMOVE 更新表
- Phase C 接入建议

## 结束条件

完成上述内容后立即停止。

最终回复：

```text
Phase B completed.

Planner is the authoritative intelligent control owner.
TaskRouter remains deterministic preflight.
Canonical Plan is the stable plan boundary.
Overall Router has been retired from the active control plane.
Runtime Kernel remains unchanged.

Phase C Skill Framework has NOT started.
```
