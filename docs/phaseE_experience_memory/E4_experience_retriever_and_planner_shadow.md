# Phase E4：ExperienceRetriever 与 Planner Shadow

## 目标
让 Planner 能读取 Experience，但先只用于 shadow reasoning / trace，不改变真实 plan。

## ExperienceRetriever 输入
```text
CanonicalGoal
course
capability
problem_type
selected_skills
risk
budget
planner_version
context feature summary
```

## 只检索
默认只返回：
- active
- scope compatible
- non-expired
- version compatible
- policy allowed
- privacy allowed

## 输出
bounded top-k `ExperienceMatch`：

```text
experience_id
type
score
match_reasons
strategy_summary
failure_warning
evidence_level
confidence
scope
version
```

## 检索策略
优先：
- capability/course/problem type
- skill overlap
- risk compatibility
- strategy prerequisites
- failure pattern
- version compatibility

可使用语义 rerank，但必须有 deterministic filter。

## Planner Shadow

```text
Planner without experience → baseline plan
Planner + ExperienceRetriever → shadow plan
```

比较：
- selected capability
- skills
- tools
- plan shape
- risk/budget
- failure avoidance
- latency/cost

真实执行继续 baseline。

## 禁止
- Experience 直接指定未注册 Skill/Tool；
- 覆盖 TaskRouter preflight；
- 绕过 SkillPolicy；
- 改变默认真实 plan；
- 跨用户检索 user-scoped 经验。

## 本阶段不 commit
完成后继续 E5。
