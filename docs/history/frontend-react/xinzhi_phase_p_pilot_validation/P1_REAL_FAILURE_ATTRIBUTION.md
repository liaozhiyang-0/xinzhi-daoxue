# P1：真实问题归因

## 分类
Product：
ui / upload / sse / session / retry / resume / review_flow / math_render / localization

Agent：
goal_understanding / planner / capability_selection / skill_selection / rag / tool / vision / model_generation / verification / reflection / experience

Governance：
permission / evidence / citation / publish_boundary / human_review

Infrastructure：
provider / database / queue / storage / vector_store / timeout

## 每个问题记录
```text
issue_id
pilot_cases
severity
frequency
user_impact
reproducible
owner
root_cause_confidence
evidence
suggested_fix_scope
```

## 优先级
`severity × frequency × user impact × reproducibility`

输出 Top 15 Failure Patterns，只选择 Top 5–8 进入第一轮修复。
