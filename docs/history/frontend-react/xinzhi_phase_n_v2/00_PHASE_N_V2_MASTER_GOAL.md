# 芯智导学 Phase N v2：Control Plane Convergence

## 阶段定位

Phase M 已完成 React 工作台、六案例展示规范、中文界面治理、统一 Markdown/KaTeX 数学渲染，并验证了 AC-01 真实图片链和 TP-01 `waiting_review` 人工复核门。

因此 Phase N v2 不再进行前端重构，也不再改演示布局。

本阶段唯一核心目标：

> 把当前“旧 Router 为默认控制面、Planner/Skill 为迁移中控制面”的过渡架构，安全收敛为 Planner + Capability + Skill + CanonicalPlan 驱动的单一生产控制面。

## M 阶段必须带入的事实

1. React 已是主工作台，主路径走 `/api/v1/tasks`。
2. 六案例统一展示链已经固定：
   `任务理解 → 任务规划 → 能力调用 → 证据准备 → 结果复核 → 结果提交`。
3. `MarkdownRenderer` + `remark-math` + `rehype-katex` 已成为统一公式渲染链。
4. 已有 31 条数学夹具。
5. AC-01 已通过真实图片上传 → Task → 视觉模型 → 结构化结果。
6. TP-01 已验证可以进入 `waiting_review`，不能被新 Planner 绕过。
7. 当前全量测试基线为 `1938 passed, 5 failed, 15 skipped`。
8. 这 5 个失败属于基线漂移/兼容问题，必须在 N0 单独治理，不能把它们混成 Phase N regression。

## 最终目标链

```text
React / API
    ↓
Unified Ingress
    ↓
GoalContract
    ↓
Deterministic Preflight
    ↓
Authoritative Planner
    ↓
Capability + Skill Resolution
    ↓
CanonicalPlan
    ↓
RuntimeTaskEngine
    ↓
PlanExecutor
    ├─ Capability
    ├─ Tool
    ├─ RAG
    ├─ Internal Worker
    └─ Provider
    ↓
Verification
    ↓
Reflection（按需）
    ↓
Governance / Human Review
    ↓
Result Commit / SSE / React
```

## 必须淘汰

- `/chat` 与 `/tasks` 两套独立目标理解；
- `TaskRouter` 作为最终业务 route owner；
- `OverallRoutingService` Runtime 二次路由；
- `IntentPlanCompiler` 默认生产 plan owner；
- `legacy-runtime:*` 生产执行；
- `agent_id → fixed workflow`；
- CanonicalPlan 创建后 route mutation；
- 固定 Agent 对固定输出模板的依赖。

## 必须保留

- React 三栏演示结构；
- 六案例中文展示规范；
- 统一 MarkdownRenderer；
- 31+ 数学公式夹具；
- `waiting_review` / `waiting_user`；
- AC-01 附件上传与视觉链；
- Task / AgentRun / checkpoint / resume；
- SSE sequence；
- Verification / Evidence / Permission / Governance；
- 六案例业务语义；
- 旧 checkpoint 的兼容读取能力。

## 执行顺序

N0 基线漂移治理与控制面审计
N1 Unified Ingress + GoalContract
N2 Planner Shadow 真实性提升
N3 Capability / Skill 生产化
N4 CanonicalPlan → Runtime 单向执行
N5 Controlled Takeover
N6 退休 Overall Router / IntentPlanCompiler
N7 退休 Legacy Runtime / Fixed Agent Workflow
N8 Presentation 解耦与前端兼容验证
N9 Active Takeover + Full Regression
N10 删除旧路径、文档收口、Git Release

## Git

N0-N9 本地连续执行，不逐阶段 commit/push。

N10 最终统一：

```text
git commit -m "refactor(agent): converge on planner-driven control plane"
git push origin agentic/planner-control-plane
```

如果 CI 仅因 Phase N regression 失败，可追加一个最小 `fix(ci)` commit。
