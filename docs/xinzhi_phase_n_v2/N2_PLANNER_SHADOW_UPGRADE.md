# N2：Planner Shadow 真实性提升

## 目标

不要直接 active takeover。

先让 Planner 真正脱离“旧 route/plan 适配器”角色。

## Planner 输入

GoalContract + CapabilityRegistry + SkillRegistry + ToolRegistry + Policy + ContextSummary + Experience prior（可选）。

## Planner 输出

CanonicalPlan。

## 必须改进

GoalInterpreter 需要真正做：
- goal normalization
- subgoal decomposition
- constraints extraction
- expected result form
- evidence/risk need

CandidateBuilder 不应只复制旧 RouteDecision。

## Shadow 比较

对六案例和代表性任务比较：

```text
legacy route/plan
vs
planner capability/skills/plan
```

指标：
- capability correctness
- plan validity
- missing prerequisite
- invalid target
- unnecessary nodes
- verification coverage
- cost/latency estimate

## Planner Mode

收敛为：

`PLANNER_MODE=shadow|controlled|active`

不再继续增加新的 planner 布尔开关。

## Gate

只有 Shadow 达到既定覆盖标准才能进入 N3/N5 controlled takeover。

本阶段不 commit。
