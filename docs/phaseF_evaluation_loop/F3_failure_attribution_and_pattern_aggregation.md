# Phase F3：Failure Attribution 与 Pattern Aggregation

## 目标
把单个失败聚合成可行动的 Failure Pattern。

## Failure Attribution
允许 deterministic rules + bounded analyst worker，但模型归因必须引用 trace evidence。

输出至少：
```text
primary_stage
component
contributing_factors
evidence_refs
confidence
alternative_causes
reproducibility
```

## Failure Pattern
聚合维度：
- course
- task family
- problem type
- capability
- skill
- tool
- planner version
- model/provider
- failure stage
- error code
- input mode
- evidence quality

## 防止错误聚合
Provider 临时 outage、单次 timeout、fixture bug、synthetic-only artifact 不能直接泛化为长期策略失败。

## 336-case
优先将此前全量 336-case 测试导入统一 failure attribution，输出：
- top failure stages
- top course/problem patterns
- high-cost low-quality patterns
- regression clusters
- route/skill/tool mismatch clusters

## 本阶段不 commit
完成后继续 F4。
