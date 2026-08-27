# P3：Agent Quality 定向优化

## 只优化 Pilot 真实暴露的问题

优先顺序：
1. Goal misunderstanding
2. Capability selection
3. Skill selection
4. Deterministic Tool / Verification
5. RAG
6. Prompt / Model generation
7. Reflection
8. Experience prior
9. Planner policy

## 禁止
- 为单一案例硬编码
- 增加固定 Agent ID
- 恢复旧 Router / legacy workflow
- 用更贵模型掩盖系统问题
- 降低验证阈值换分数

## Proposal
```text
pattern_id
root_cause
target_component
minimal_change
baseline_cases
candidate_cases
score_delta
new_regressions
latency_delta
cost_delta
decision
```

最多 2–3 轮，每轮 3–5 个问题。

## 六案例边界
- TP：教师复核
- FE：不自动总分
- LP：不宣称已掌握
- RB：不虚构 DOI / 定量结论
- KG：不自动发布
- AC：不编造图像事实
