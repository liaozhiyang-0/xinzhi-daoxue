# Phase B1：Planner Contract 与唯一 Owner 建立

## 目标

建立 Planner 的稳定 contract 和代码边界，但暂不影响真实执行路径。

Planner 的职责：

```text
Goal Understanding
+ Candidate Capability Selection
+ Skill/Tool/Agent Candidate Selection
+ Canonical Plan Proposal
+ Budget / Success Criteria / Constraints
+ Lineage
```

Planner 不负责执行 Provider、Tool、RAG，不修改 Task terminal state，不直接写 Session Memory，不绕过 TaskRouter preflight，也不管理 Runtime checkpoint。

## 非协商设计

Planner 必须输出一个可序列化、可版本化、可 checkpoint/trace 的 `PlannerSnapshot` 或等价结构。

建议语义：

```text
PlannerSnapshot
  planner_version
  goal
  objective
  task_family
  course
  intent
  candidate_capabilities
  selected_capability
  selected_agents
  selected_skills
  selected_tools
  success_criteria
  constraints
  budget
  context_requirements
  canonical_plan
  confidence
  reason_codes
  lineage
```

具体字段可以根据现有 contract 做 additive 调整，但语义不可偏离。

## 必须完成

1. 新增 Planner contract。
2. 定义 PlannerService 接口。
3. 定义 GoalInterpreter / CandidateBuilder / PlanCompiler 的内部边界。
4. 明确 Planner 与 Supervisor、TaskRouter、AgentRegistry、SkillRegistry、ToolRegistry、Runtime 的依赖方向。
5. Planner 只能读取 Registry/Context/Policy snapshot，不得执行能力。
6. 建立 Planner feature flag，默认 OFF 或 SHADOW。
7. Planner 输出必须可记录到 trace，但不能改变当前 route。

## 禁止

- 不接管 `/chat` 或 `/tasks`；
- 不删除旧 Router；
- 不接管 Overall Router；
- 不实现 SkillRetriever；
- 不修改 Runtime 真实 plan；
- 不引入自由递归 Agent loop。

## 交付物

- Planner contract
- PlannerService skeleton
- planner owner / dependency architecture doc
- contract tests
- feature flag

## 结束条件

- Planner contract 可独立序列化/反序列化；
- PlannerService 可在 isolated test 中生成 deterministic/mock snapshot；
- 不影响当前真实任务结果；
- feature flag 默认不改变执行路径；
- 测试通过。

最终回复：

```text
Phase B1 completed.
Planner contract and owner established.
Production routing unchanged.
Stopped before B2.
```
