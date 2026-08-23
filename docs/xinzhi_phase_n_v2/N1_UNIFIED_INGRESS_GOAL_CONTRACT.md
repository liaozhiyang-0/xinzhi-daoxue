# N1：Unified Ingress + GoalContract

## 目标

统一 `/chat` 和 `/tasks` 的目标理解，但保持 React 当前 `/tasks` 主路径不变。

## 结构

```text
/chat adapter ─┐
               ├→ UnifiedRequestPreparation
/tasks ────────┘
               ↓
           GoalContract
```

## UnifiedRequestPreparation

负责：
- user/session identity
- scenario/course hints
- attachments
- content extraction
- input modality
- session continuity
- safety preflight
- request normalization

不负责最终业务规划。

## GoalContract

至少：
goal_id、normalized_goal、user_role、course_context、task_family_hint、input_modalities、constraints、desired_output、evidence_requirements、risk_level、budget、attachment refs、session context ref。

## Phase M 兼容要求

- AC-01 图片仍通过既有 File upload → Task 链；
- `waiting_review` / `waiting_user` 状态不变；
- 六案例 scenario hint 只能作为 Planner hint，不能硬指定最终 Agent。

## 验收

同一语义输入经 `/chat` 与 `/tasks`：
`GoalContract semantic equivalence = PASS`

本阶段不 commit。
