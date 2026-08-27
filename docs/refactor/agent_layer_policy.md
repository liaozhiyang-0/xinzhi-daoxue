# Agent 层级策略

## 1. 结论

当前内部 Worker 数量多，但不应继续通过 public Agent ID 扩展控制面。领域能力保留为 Public Capability；分类、改写、抽取、规划和审核等内部角色保持内部 Worker 身份，未来通过 Skill/Tool/Worker 组合复用。

处理分类：

| 层级 | 处理 | 规则 |
| --- | --- | --- |
| Public Capability | KEEP | 面向用户任务、可被 Registry 路由和审计 |
| Internal Worker | KEEP / FREEZE | 可被业务 Runtime 或内部 Hub 调用，不成为 public Agent |
| 未来 Skill | DESIGN ONLY | 本阶段不创建 SkillRegistry、SkillRetriever 或目录 |
| 重复 public Agent | REMOVE（未来，需迁移方案） | 不在本阶段删除 Agent ID 或配置 |

## 2. Public Capability 边界

以下是应保留的稳定业务能力族：

- `ACADEMIC_PROBLEM_SOLVER`：电子信息课程问题求解，统一承接电路题能力；
- `TEACHING`：教案、作业、教学反馈等教学能力族；
- `KNOWLEDGE`：课程知识问答、检索增强和解释；
- `RESEARCH`：学术检索、学术写作、数据分析和证据简报。

实际 public Agent ID 仍以 `agent_configs/registry.yaml` 和已发布状态为准；本阶段不新增、不删除、不修改 Agent ID。

Public Capability 必须具备：

- Registry descriptor、版本和 publication status；
- `AgentRequest -> AgentResult` 兼容输入/输出契约；
- 明确 RAG、Tool、附件和 evidence policy；
- 可被 Task Runtime 启动、checkpoint 和恢复；
- 可在 Evaluation Framework 中按 capability 追踪。

## 3. Internal Worker 分类

现有 `InternalAgentHub` 中下列角色应保持内部身份：

| Worker 类型 | 当前示例 | 未来边界 |
| --- | --- | --- |
| Classifier | `COURSE_CLASSIFIER_LOCAL_V1`、`INTENT_CLASSIFIER_LOCAL_V1`、`RESEARCH_INTENT_CLASSIFIER_LOCAL_V1` | Planner/业务能力的内部识别步骤 |
| Router | `OVERALL_ROUTER_LOCAL_V1` | 过渡期路由 Worker；未来并入 Planner |
| Query Rewriter | `QUERY_REWRITER_LOCAL_V1` | Knowledge/RAG Skill 的内部步骤 |
| Vision Extractor | `CIRCUIT_VISION_EXTRACTOR_LOCAL_V1` | Academic Solver 的输入 Tool/Worker |
| Circuit Planner | `CIRCUIT_PLANNER_LOCAL_V1` | Academic Solver Skill 的规划步骤 |
| Research Planner/Reviewer | `ACADEMIC_SEARCH_PLANNER_LOCAL_V1`、`ACADEMIC_PAPER_REVIEW_LOCAL_V1` | Research Skill 的内部步骤 |
| Composer/Explainer | `RESEARCH_FRONTIER_BRIEF_LOCAL_V1` 等 | Research/Teaching/Knowledge 的输出 Worker |

内部 Worker 的结果必须绑定 request/run/trace identity，不直接改变 Task 状态，不绕过 Agent Registry 或 Runtime policy。

## 4. Agent / Skill / Tool / Worker 边界

```text
Public Capability
  -> Skill（未来可复用的专业能力）
      -> Tool（确定性外部/本地操作）
      -> Worker（模型或内部处理角色）
```

- Agent/Public Capability：面向用户的任务入口和发布单元。
- Skill：可跨 Public Capability 复用、可版本化、可评估的能力组合；本阶段只设计不实现。
- Tool：有明确输入输出、权限、预算和副作用声明的操作；不得隐藏路由。
- Worker：内部执行角色；不能因为有独立 prompt 或 output schema 就升级为 public Agent。

## 5. KEEP / MERGE / FREEZE / REMOVE

### KEEP

- Public Capability 与已发布 Agent Registry contract；
- Academic Solver、Teaching、Knowledge、Research Runtime；
- InternalAgentHub 作为内部 Worker 调用边界。

### MERGE（未来）

- Classifier/Router 的目标理解并入 Planner；
- Query Rewriter、Vision Extractor、Reviewer 等按领域并入 Skill/Tool/Worker 组合；
- 重复的 public Agent 入口收敛到 capability + skill。

### FREEZE

- 退役的 `SOLVER_CT v1.0` 历史标识及其专用控制面；
- `OVERALL_ROUTER_LOCAL_V1` 及其他内部 Worker ID；
- Public Agent 的现有 input/output/event contract。

### REMOVE

- 本 Phase A 不删除任何 Agent ID、配置或 Worker。
- 未来只有在迁移、回滚、contract tests 和评测证据齐备后，才可移除重复 public 入口。
