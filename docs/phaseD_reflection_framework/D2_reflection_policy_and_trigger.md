# Phase D2：ReflectionPolicy 与触发策略

## 目标
决定什么时候需要 Critic，避免每个任务都增加模型调用。

## 输入
capability/task family、complexity、risk、evidence quality、deterministic verification、selected skills、result confidence、fallback/degraded status、unsupported claims、scenario、budget/latency。

## 输出
```text
ReflectionDecision
  action: skip | critique | needs_review | fail
  reason_codes
  max_revision_count
  critic_profile
  budget
  required_verifiers
```

## 默认策略
强触发候选：复杂学术求解、verification 异常、Research evidence conflict、Knowledge 证据不足却需生成、Academic writing unsupported claims。
可跳过：简单低风险、retrieval-only、已被确定性工具完整验证、明确能力不足的 fallback。

## 约束
- 默认 `max_revision_count = 1`
- Critic 有独立预算
- ReflectionPolicy 不是新 Planner
- Critic 无权再次触发 Critic

## 测试
覆盖 should-trigger / should-skip / fail-review / budget exhausted。

## 提交
本阶段不 commit，完成后继续 D3。
