# N5：Controlled Takeover

## 目标

先在已验证场景上让新控制面真正执行。

## 第一批

优先六案例：

TP-01 / FE-01 / LP-01 / RB-01 / KG-01 / AC-01

因为 Phase M 已建立前端契约和专项测试。

## 第二批

再覆盖：
Academic Solver / Knowledge QA / General / Research / Teaching 常规任务。

## Controlled 模式

Planner 负责：
Goal → Capability → Skill → CanonicalPlan

旧 Router 只作为对照/紧急 fallback。

## 必测

- TP-01 `waiting_review`
- AC-01 real image upload
- FE-01 no auto-score
- LP-01 no false mastery
- RB-01 no fabricated DOI
- KG-01 no auto-publish

## Gate

critical regression = 0
invalid capability = 0
unregistered skill/tool = 0
waiting_review preserved
AC-01 upload preserved
SSE order preserved

本阶段不 commit。
