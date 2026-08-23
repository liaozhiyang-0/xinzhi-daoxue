# T2：Failure Attribution 与 Top Failure Patterns

## 目标
把 T1 的失败案例转换为可行动的问题模式。

## Failure Stage
input / routing / planner / skill_selection / rag / tool / model_generation / reflection / verification / governance / runtime / fixture / unknown

## 每个失败必须回答
What failed? Where? Evidence? Owner? Reproducible? Severity?

## Failure Pattern
按 course、task type、problem type、difficulty、input mode、skill、tool、model、failure stage、error code 聚合。

至少输出 Top 20 Failure Patterns。

每个 pattern：
pattern_id、case_count、failure_rate、severity、representative_cases、owner_component、evidence、likely_root_cause、recommended_action。

## 优先级
Priority = frequency × severity × user impact × fixability。

第一轮只选 Top 5 进入 T3。

## 提交
`test(eval): complete failure attribution analysis`
