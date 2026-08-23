# Codex Phase N v2 完整执行指令

执行“芯智导学 Phase N v2：Control Plane Convergence”。

## Phase M 已知稳定基线

- React 主工作台已完成；
- 六案例前端规范已完成；
- `MarkdownRenderer` + KaTeX 已完成；
- 31 条数学 fixture 已通过；
- AC-01 真实图片链已通过；
- TP-01 `waiting_review` 已通过；
- 当前全量 pytest 基线为 `1938 passed, 5 failed, 15 skipped`。

不要重新设计前端，不要重新实现公式渲染。

## 执行顺序

N0 → N1 → N2 → N3 → N4 → N5 → N6 → N7 → N8 → N9 → N10

## 核心目标

淘汰：
- OverallRoutingService 生产二次路由
- fixed Agent ID 业务路由
- legacy-runtime 生产执行
- IntentPlanCompiler 默认生产 plan
- `/chat` 与 `/tasks` 双目标理解
- CanonicalPlan 后 route mutation

建立：
GoalContract → Planner → Capability + Skill → CanonicalPlan → Runtime

## 关键安全要求

- `waiting_review` / `waiting_user` 必须保持；
- AC-01 不得编造图像事实；
- FE-01 不自动总分；
- LP-01 不宣称已掌握；
- RB-01 不虚构 DOI；
- KG-01 不自动发布；
- Runtime 不重新理解用户目标；
- Planner 不自创未注册 capability/skill/tool。

## Phase M 5 个失败

N0 必须先分类。

不得简单改数量断言来“让测试绿”。

必须先判断是：
- intended catalog expansion
- API filtering semantics
- stale fixture
- actual embedding compatibility bug

然后再修。

## Git

N0-N9 不逐阶段 commit/push。

N10 统一：

`git commit -m "refactor(agent): converge on planner-driven control plane"`

push + CI，不自动 merge main。

## 最终交付

- `docs/architecture/phase_n_control_plane_closeout.md`
- `docs/architecture/phase_n0_baseline_drift.md`
- `docs/architecture/phase_n8_takeover_evaluation.md`

完成后停止，等待重新启动 T0 Benchmark。
